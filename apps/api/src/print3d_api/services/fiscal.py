"""Nota fiscal própria (NF-e 55) a partir dos pedidos — direto na SEFAZ, sem terceiros.

Fluxo: dados do destinatário (cliente do site ou faturamento do comprador no ML) → número
reservado no banco → XML assinado com o A1 → SEFAZ. Autorizada: XML vai para a venda no ML
e o dono recebe por e-mail a nota + o link da etiqueta de envio.

Tudo que é dado da empresa (IE, endereço, CFOP, NCM, CSOSN...) vem de Integrações → Nota
fiscal; o certificado A1 e a senha ficam cifrados no banco (Fernet).
"""

import base64
import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.models import (
    ChannelAccount,
    Customer,
    FiscalInvoice,
    Order,
    OrderEvent,
    OrderItem,
    Variant,
)
from print3d_api.models.catalog import Product
from print3d_api.services import audit, integrations, mailer
from print3d_api.services import mercadolivre as ml
from print3d_api.services.cep import CepError, CepProvider
from print3d_channels.mercadolivre import MercadoLivreError
from print3d_core.security import TokenVaultError
from print3d_fiscal import (
    Certificado,
    CertificadoError,
    Destinatario,
    Emitente,
    Endereco,
    Intermediador,
    Item,
    Nota,
    NotaError,
    Pagamento,
    Sefaz,
    SefazError,
    Transmissor,
    carregar_pfx_base64,
    montar,
    nfe_proc,
)
from print3d_fiscal.xmlc import so_digitos

log = logging.getLogger("print3d.fiscal")
BRT = ZoneInfo("America/Sao_Paulo")
LABEL_TTL = int(timedelta(days=30).total_seconds())
FINAL = ("autorizada", "cancelada", "denegada")
TPAG = {"pix_manual": "17", "pix_mercadopago": "17", "cartao_mercadopago": "03"}


class FiscalError(Exception):
    def __init__(self, message: str, *, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


# --- Configuração ---------------------------------------------------------------------------
REQUIRED = {
    "FISCAL_RAZAO_SOCIAL": "razão social",
    "FISCAL_IE": "inscrição estadual",
    "FISCAL_CEP": "CEP da empresa",
    "FISCAL_NUMERO": "número do endereço",
    "FISCAL_NCM_PADRAO": "NCM padrão",
    "FISCAL_CFOP_INTERNA": "CFOP dentro do estado",
    "FISCAL_CFOP_INTERESTADUAL": "CFOP para outro estado",
    "FISCAL_CERT_PFX": "certificado A1",
    "FISCAL_CERT_SENHA": "senha do certificado",
}


async def _values(session: AsyncSession) -> dict[str, str]:
    db = await integrations.load(session)
    keys = [f.key for f in integrations.FIELDS if f.group == "notafiscal"]
    return {k: (db.get(k) or integrations.env_value(k) or "").strip() for k in keys}


def ambiente(values: dict[str, str]) -> int:
    return 1 if values.get("FISCAL_AMBIENTE") == "producao" else 2


def serie(values: dict[str, str]) -> int:
    raw = values.get("FISCAL_SERIE", "")
    return int(raw) if raw.isdigit() else 1


def _certificate(values: dict[str, str]) -> Certificado:
    if not values.get("FISCAL_CERT_PFX") or not values.get("FISCAL_CERT_SENHA"):
        raise FiscalError("envie o certificado A1 e a senha (painel → Nota fiscal)", status=409)
    try:
        return carregar_pfx_base64(values["FISCAL_CERT_PFX"], values["FISCAL_CERT_SENHA"])
    except CertificadoError as exc:
        raise FiscalError(f"certificado: {exc}", status=409) from exc


def _cert_info(cert: Certificado) -> dict[str, Any]:
    return {
        "titular": cert.titular,
        "cnpj": cert.cnpj,
        "valido_ate": cert.valido_ate.isoformat(),
        "vencido": cert.vencido(),
    }


async def next_number(session: AsyncSession, values: dict[str, str]) -> int:
    last = await session.scalar(
        select(func.max(FiscalInvoice.number)).where(
            FiscalInvoice.ambiente == ambiente(values), FiscalInvoice.serie == serie(values)
        )
    )
    start = values.get("FISCAL_NUMERO_INICIAL", "")
    return max(int(start) if start.isdigit() else 1, (last or 0) + 1)


async def status(session: AsyncSession) -> dict[str, Any]:
    values = await _values(session)
    missing = [label for key, label in REQUIRED.items() if not values.get(key)]
    cert: dict[str, Any] | None = None
    cert_error = None
    if values.get("FISCAL_CERT_PFX") and values.get("FISCAL_CERT_SENHA"):
        try:
            cert = _cert_info(_certificate(values))
        except FiscalError as exc:
            cert_error = str(exc)
    smtp = await mailer.settings(session)
    return {
        "ready": not missing and cert is not None and not cert["vencido"],
        "missing": missing,
        "ambiente": "producao" if ambiente(values) == 1 else "homologacao",
        "serie": serie(values),
        "next_number": await next_number(session, values),
        "certificate": cert,
        "certificate_error": cert_error,
        "email_ready": smtp is not None and bool(smtp.owner),
    }


async def save_certificate(session: AsyncSession, data: bytes, senha: str) -> dict[str, Any]:
    if not data or len(data) > 64_000:
        raise FiscalError("arquivo de certificado vazio ou grande demais (o A1 tem poucos KB)")
    b64 = base64.b64encode(data).decode()
    try:
        cert = carregar_pfx_base64(b64, senha)
    except CertificadoError as exc:
        raise FiscalError(str(exc)) from exc
    if not cert.cnpj:
        raise FiscalError("não achei CNPJ no certificado: precisa ser e-CNPJ A1")
    if cert.vencido():
        raise FiscalError("certificado vencido ou ainda não válido")
    try:
        await integrations.save(
            session, {"FISCAL_CERT_PFX": b64, "FISCAL_CERT_SENHA": senha}, [], actor="admin"
        )
    except integrations.IntegrationError as exc:
        raise FiscalError(str(exc), status=503) from exc
    return _cert_info(cert)


TransmissorFactory = Callable[[Certificado, int], Transmissor]


def default_transmissor(cert: Certificado, amb: int) -> Transmissor:
    return Sefaz(cert, ambiente=amb)


async def sefaz_status(
    session: AsyncSession, factory: TransmissorFactory = default_transmissor
) -> dict[str, Any]:
    values = await _values(session)
    cert = _certificate(values)
    try:
        ret = await factory(cert, ambiente(values)).status()
    except SefazError as exc:
        raise FiscalError(str(exc), status=502) from exc
    return {"cstat": ret.cstat, "motivo": ret.motivo, "online": ret.cstat == "107"}


# --- Destinatário -----------------------------------------------------------------------------
@dataclass
class Recipient:
    nome: str = ""
    documento: str = ""
    email: str | None = None
    ie: str | None = None
    cep: str = ""
    logradouro: str = ""
    numero: str = ""
    complemento: str | None = None
    bairro: str = ""
    municipio: str = ""
    uf: str = ""
    cod_municipio: str = ""

    def missing(self) -> list[str]:
        out = []
        if not self.nome.strip():
            out.append("nome")
        if len(so_digitos(self.documento)) not in (11, 14):
            out.append("CPF/CNPJ")
        if len(so_digitos(self.cep)) != 8:
            out.append("CEP")
        for campo in ("logradouro", "bairro", "municipio", "uf"):
            if not str(getattr(self, campo)).strip():
                out.append(campo)
        return out

    def as_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def _info(items: list[dict[str, Any]], *types: str) -> str:
    for t in types:
        for row in items:
            if str(row.get("type", "")).upper() == t and row.get("value"):
                return str(row["value"])
    return ""


def parse_ml_billing(data: dict[str, Any]) -> Recipient:
    """Aceita o formato novo (/orders/billing-info) e o antigo (x-version 2)."""
    r = Recipient()
    buyer = data.get("buyer") or {}
    info = buyer.get("billing_info") or data.get("billing_info") or data
    ident = info.get("identification") or {}
    extra = info.get("additional_info") or []
    r.documento = so_digitos(
        str(ident.get("number") or info.get("doc_number") or _info(extra, "DOC_NUMBER"))
    )
    business = info.get("business_name") or _info(extra, "BUSINESS_NAME")
    nome = " ".join(
        p
        for p in (
            info.get("name") or _info(extra, "FIRST_NAME"),
            info.get("last_name") or _info(extra, "LAST_NAME"),
        )
        if p
    )
    r.nome = str(business or nome).strip()
    r.ie = so_digitos(str(info.get("state_registration") or _info(extra, "STATE_REGISTRATION")))
    r.ie = r.ie or None
    addr = info.get("address") or {}
    state = addr.get("state") or {}
    r.logradouro = str(addr.get("street_name") or _info(extra, "STREET_NAME"))
    r.numero = str(addr.get("street_number") or _info(extra, "STREET_NUMBER"))
    r.complemento = str(addr.get("comment") or _info(extra, "COMMENT")) or None
    r.bairro = str(addr.get("neighborhood") or _info(extra, "NEIGHBORHOOD"))
    r.municipio = str(addr.get("city_name") or _info(extra, "CITY_NAME"))
    uf = state.get("code") if isinstance(state, dict) else state
    r.uf = str(uf or _info(extra, "STATE_CODE")).upper().replace("BR-", "")[:2]
    r.cep = so_digitos(str(addr.get("zip_code") or _info(extra, "ZIP_CODE")))
    return r


async def _complete_address(r: Recipient, cep: CepProvider) -> Recipient:
    """Código IBGE (e o que faltar de cidade/UF/bairro/rua) pelo CEP."""
    if len(so_digitos(r.cep)) != 8:
        return r
    try:
        a = await cep.lookup(r.cep)
    except CepError:
        return r
    r.cod_municipio = r.cod_municipio or a.ibge
    r.municipio = r.municipio or a.city
    r.uf = r.uf or a.uf
    r.bairro = r.bairro or a.district
    r.logradouro = r.logradouro or a.street
    return r


async def _ml_order(session: AsyncSession, order: Order) -> dict[str, Any]:
    token = await ml.access_token(session)
    client = await ml.client(session)
    return await client.get(token, f"/orders/{order.external_id}")


async def prefill(session: AsyncSession, order: Order, cep: CepProvider) -> dict[str, Any]:
    """Destinatário sugerido para o formulário (o dono confere e corrige antes de emitir)."""
    r = Recipient()
    note = None
    if order.channel == ml.CHANNEL and order.external_id:
        try:
            token = await ml.access_token(session)
            client = await ml.client(session)
            ml_order = await client.get(token, f"/orders/{order.external_id}")
            r = parse_ml_billing(await client.billing_info(token, ml_order))
        except (ml.MLError, MercadoLivreError) as exc:
            note = f"não consegui ler os dados de faturamento no ML: {exc}"
    else:
        customer = await session.get(Customer, order.customer_id) if order.customer_id else None
        addr = order.shipping_address or {}
        if customer:
            r.nome = customer.legal_name or customer.name
            r.documento = so_digitos(customer.document)
            r.email = customer.email
        r.cep = so_digitos(str(addr.get("cep", "")))
        r.logradouro = str(addr.get("street") or "")
        r.numero = str(addr.get("number") or "")
        r.complemento = addr.get("complement") or None
        r.bairro = str(addr.get("district") or "")
        r.municipio = str(addr.get("city") or "")
        r.uf = str(addr.get("uf") or "")
    r = await _complete_address(r, cep)
    return {"recipient": r.as_dict(), "missing": r.missing(), "note": note}


# --- Emissão --------------------------------------------------------------------------------
async def _emitente(values: dict[str, str], cert: Certificado, cep: CepProvider) -> Emitente:
    try:
        a = await cep.lookup(values["FISCAL_CEP"])
    except CepError as exc:
        raise FiscalError(f"CEP da empresa: {exc}") from exc
    crt = values.get("FISCAL_CRT") or "4"
    return Emitente(
        cnpj=cert.cnpj or "",
        razao_social=values["FISCAL_RAZAO_SOCIAL"],
        nome_fantasia=values.get("FISCAL_NOME_FANTASIA") or None,
        ie=values["FISCAL_IE"],
        crt=int(crt),
        endereco=Endereco(
            logradouro=values.get("FISCAL_LOGRADOURO") or a.street,
            numero=values["FISCAL_NUMERO"],
            complemento=values.get("FISCAL_COMPLEMENTO") or None,
            bairro=values.get("FISCAL_BAIRRO") or a.district,
            cod_municipio=a.ibge,
            municipio=a.city,
            uf=a.uf,
            cep=a.cep,
            fone=values.get("FISCAL_FONE") or None,
        ),
    )


async def _items(
    session: AsyncSession, order: Order, values: dict[str, str], interna: bool
) -> tuple[Item, ...]:
    rows = (
        await session.scalars(
            select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.id)
        )
    ).all()
    cfop = values["FISCAL_CFOP_INTERNA"] if interna else values["FISCAL_CFOP_INTERESTADUAL"]
    out = []
    for row in rows:
        ncm, codigo = values["FISCAL_NCM_PADRAO"], row.sku or f"ITEM{row.id}"
        if row.variant_id:
            variant = await session.get(Variant, row.variant_id)
            product = await session.get(Product, variant.product_id) if variant else None
            if variant:
                codigo = variant.sku
            if product and product.ncm:
                ncm = product.ncm
        out.append(
            Item(
                codigo=codigo,
                descricao=row.title,
                ncm=ncm,
                cfop=cfop,
                quantidade=Decimal(row.quantity),
                valor_unitario=row.unit_price,
                csosn=values.get("FISCAL_CSOSN") or "102",
            )
        )
    if not out:
        raise FiscalError("pedido sem itens")
    return tuple(out)


async def _reserve(session: AsyncSession, order: Order, values: dict[str, str]) -> FiscalInvoice:
    """Reaproveita a tentativa rejeitada do pedido (mesmo número); senão reserva o próximo."""
    rows = (
        await session.scalars(
            select(FiscalInvoice)
            .where(FiscalInvoice.order_id == order.id, FiscalInvoice.ambiente == ambiente(values))
            .order_by(FiscalInvoice.id.desc())
        )
    ).all()
    for inv in rows:
        if inv.status == "autorizada":
            raise FiscalError(f"este pedido já tem a NF-e nº {inv.number} autorizada", status=409)
        if inv.status in ("processando", "sem_resposta"):
            raise FiscalError(
                f"a NF-e nº {inv.number} ficou sem resposta da SEFAZ: clique em Consultar antes "
                "de emitir de novo (evita nota em dobro)",
                status=409,
            )
    retry = next((i for i in rows if i.status == "rejeitada"), None)
    if retry is not None:
        return retry
    inv = FiscalInvoice(
        order_id=order.id,
        ambiente=ambiente(values),
        serie=serie(values),
        number=await next_number(session, values),
        status="processando",
        total=Decimal(0),
        recipient={},
    )
    session.add(inv)
    await session.flush()
    return inv


async def emit(
    session: AsyncSession,
    order_id: int,
    recipient: dict[str, Any] | None,
    cep: CepProvider,
    factory: TransmissorFactory = default_transmissor,
) -> FiscalInvoice:
    order = await session.get(Order, order_id)
    if order is None:
        raise FiscalError("pedido não existe", status=404)
    if order.status in ("aguardando_pagamento", "cancelado"):
        raise FiscalError("só dá para emitir nota de pedido pago e não cancelado")
    values = await _values(session)
    missing = [label for key, label in REQUIRED.items() if not values.get(key)]
    if missing:
        raise FiscalError("falta configurar em Integrações → Nota fiscal: " + ", ".join(missing))
    cert = _certificate(values)
    if cert.vencido():
        raise FiscalError("certificado A1 vencido: envie o novo no painel", status=409)

    if recipient is None:
        r = Recipient(**(await prefill(session, order, cep))["recipient"])
    else:
        allowed = set(Recipient.__dataclass_fields__)
        r = Recipient(**{k: v for k, v in recipient.items() if k in allowed})
    r = await _complete_address(r, cep)
    if r.missing():
        raise FiscalError("dados do destinatário incompletos: " + ", ".join(r.missing()))
    emit_ = await _emitente(values, cert, cep)
    interna = r.uf.upper() == emit_.endereco.uf.upper()
    items = await _items(session, order, values, interna)

    pagamentos: tuple[Pagamento, ...] = ()
    intermediador = None
    is_ml = order.channel == ml.CHANNEL
    if is_ml:
        account = await session.get(ChannelAccount, ml.CHANNEL)
        cnpj_ml = so_digitos(values.get("FISCAL_ML_CNPJ"))
        if len(cnpj_ml) != 14:
            raise FiscalError("venda do ML: preencha o CNPJ do Mercado Livre em Nota fiscal")
        intermediador = Intermediador(cnpj_ml, (account.nickname if account else None) or "ML")
        pagamentos = (Pagamento("99", Decimal(0), "Mercado Pago"),)
    elif order.payment_method in TPAG:
        pagamentos = (Pagamento(TPAG[order.payment_method], Decimal(0)),)

    frete = Decimal(0) if is_ml else (order.shipping or Decimal(0))
    inv = await _reserve(session, order, values)
    nota = Nota(
        emitente=emit_,
        destinatario=Destinatario(
            nome=r.nome,
            documento=r.documento,
            email=r.email,
            ie=r.ie,
            endereco=Endereco(
                logradouro=r.logradouro,
                numero=r.numero or "S/N",
                complemento=r.complemento,
                bairro=r.bairro,
                cod_municipio=r.cod_municipio,
                municipio=r.municipio,
                uf=r.uf,
                cep=r.cep,
            ),
        ),
        itens=items,
        numero=inv.number,
        serie=inv.serie,
        emissao=datetime.now(BRT).replace(microsecond=0),
        ambiente=inv.ambiente,
        frete=frete,
        desconto=order.discount or Decimal(0),
        pagamentos=(),
        intermediador=intermediador,
        info_complementar=values.get("FISCAL_OBS") or None,
    )
    try:
        valor = sum((i.valor_bruto for i in items), Decimal(0)) - nota.desconto + nota.frete
        pags = tuple(Pagamento(p.tipo, valor, p.descricao) for p in pagamentos)
        montada = montar(replace(nota, pagamentos=pags), cert)
    except NotaError as exc:
        inv.status, inv.motivo = "rejeitada", f"nota não montada: {exc}"
        await session.commit()
        raise FiscalError(str(exc)) from exc

    inv.status, inv.chave, inv.xml = "processando", montada.chave, montada.xml
    inv.total, inv.recipient = montada.valor_total, r.as_dict()
    inv.cstat = inv.motivo = inv.protocolo = None
    await session.commit()  # número e chave gravados ANTES de transmitir

    try:
        ret = await factory(cert, inv.ambiente).autorizar(montada.xml)
    except SefazError as exc:
        inv.status, inv.motivo = "sem_resposta", str(exc)
        await session.commit()
        raise FiscalError(
            f"a SEFAZ não respondeu ({exc}). Clique em Consultar em alguns minutos.", status=502
        ) from exc
    await _apply_result(session, inv, order, ret.cstat, ret.motivo, ret.protocolo, ret.prot_xml)
    if inv.status == "autorizada":
        await after_authorized(session, inv, order)
    return inv


async def _apply_result(
    session: AsyncSession,
    inv: FiscalInvoice,
    order: Order,
    cstat: str,
    motivo: str,
    protocolo: str | None,
    prot_xml: str | None,
) -> None:
    inv.cstat, inv.motivo = cstat, motivo
    if cstat in ("100", "150") and prot_xml and inv.xml:
        inv.status, inv.protocolo = "autorizada", protocolo
        inv.proc_xml = nfe_proc(inv.xml, prot_xml)
        inv.authorized_at = datetime.now(UTC)
        session.add(
            OrderEvent(
                order_id=order.id,
                status=order.status,
                actor="sistema",
                note=f"Nota fiscal nº {inv.number} emitida",
            )
        )
    elif cstat in ("110", "301", "302", "303"):
        inv.status = "denegada"
    elif cstat == "105":
        inv.status = "sem_resposta"
    else:
        inv.status = "rejeitada"
    await audit.record(
        session,
        actor="admin",
        action="nfe_transmitida",
        entity_type="order",
        entity_id=order.id,
        decision=inv.status,
        reason=f"{cstat} {motivo}"[:500],
        payload={"numero": inv.number, "serie": inv.serie, "ambiente": inv.ambiente},
    )
    await session.commit()


async def consult(
    session: AsyncSession, invoice_id: int, factory: TransmissorFactory = default_transmissor
) -> FiscalInvoice:
    inv = await session.get(FiscalInvoice, invoice_id)
    if inv is None or not inv.chave:
        raise FiscalError("nota não existe", status=404)
    order = await session.get(Order, inv.order_id)
    assert order is not None
    cert = _certificate(await _values(session))
    try:
        ret = await factory(cert, inv.ambiente).consultar(inv.chave)
    except SefazError as exc:
        raise FiscalError(str(exc), status=502) from exc
    was = inv.status
    if ret.cstat == "217":  # a SEFAZ não conhece a chave: o número pode ser reenviado
        inv.status, inv.cstat, inv.motivo = "rejeitada", ret.cstat, ret.motivo
        await session.commit()
    elif ret.cstat == "101" and was == "autorizada":
        inv.status, inv.cstat, inv.motivo = "cancelada", ret.cstat, ret.motivo
        await session.commit()
    elif was != "autorizada":
        await _apply_result(session, inv, order, ret.cstat, ret.motivo, ret.protocolo, ret.prot_xml)
        if inv.status == "autorizada":
            await after_authorized(session, inv, order)
    return inv


async def cancel(
    session: AsyncSession,
    invoice_id: int,
    justificativa: str,
    factory: TransmissorFactory = default_transmissor,
) -> FiscalInvoice:
    inv = await session.get(FiscalInvoice, invoice_id)
    if inv is None or not inv.chave:
        raise FiscalError("nota não existe", status=404)
    if inv.status != "autorizada" or not inv.protocolo:
        raise FiscalError("só dá para cancelar nota autorizada")
    cert = _certificate(await _values(session))
    try:
        ret = await factory(cert, inv.ambiente).cancelar(
            inv.chave, inv.protocolo, justificativa, datetime.now(BRT).replace(microsecond=0)
        )
    except ValueError as exc:
        raise FiscalError(str(exc)) from exc
    except SefazError as exc:
        raise FiscalError(str(exc), status=502) from exc
    if ret.cstat not in ("135", "136", "155"):
        raise FiscalError(f"SEFAZ recusou o cancelamento: {ret.cstat} {ret.motivo}")
    inv.status, inv.cstat, inv.motivo = "cancelada", ret.cstat, ret.motivo
    inv.cancel_xml = ret.evento_xml
    await audit.record(
        session,
        actor="admin",
        action="nfe_cancelada",
        entity_type="order",
        entity_id=inv.order_id,
        reason=justificativa[:500],
        payload={"numero": inv.number},
    )
    await session.commit()
    return inv


# --- Depois de autorizada: XML no ML + e-mail com a etiqueta --------------------------------
def label_token(order_id: int) -> str:
    vault = integrations.vault()
    if vault is None:
        raise FiscalError("servidor sem FERNET_KEY", status=503)
    return vault.encrypt(f"etiqueta:{order_id}")


def order_from_label_token(token: str) -> int | None:
    vault = integrations.vault()
    if vault is None:
        return None
    try:
        raw = vault.decrypt(token, ttl=LABEL_TTL)
    except TokenVaultError:
        return None
    kind, _, oid = raw.partition(":")
    return int(oid) if kind == "etiqueta" and oid.isdigit() else None


async def label_pdf(session: AsyncSession, order_id: int) -> bytes:
    order = await session.get(Order, order_id)
    if order is None or order.channel != ml.CHANNEL or not order.external_id:
        raise FiscalError("etiqueta só existe para venda do Mercado Livre", status=404)
    try:
        data = await _ml_order(session, order)
        shipment = (data.get("shipping") or {}).get("id")
        if not shipment:
            raise FiscalError("essa venda não tem envio pelo Mercado Envios", status=404)
        token = await ml.access_token(session)
        return await (await ml.client(session)).shipment_label_pdf(token, str(shipment))
    except (ml.MLError, MercadoLivreError) as exc:
        raise FiscalError(f"etiqueta ainda indisponível no ML: {exc}", status=409) from exc


async def _public_api(session: AsyncSession) -> str | None:
    db = await integrations.load(session)
    base = db.get("PUBLIC_API_URL") or integrations.env_value("PUBLIC_API_URL")
    return base.rstrip("/") if base else None


async def after_authorized(session: AsyncSession, inv: FiscalInvoice, order: Order) -> None:
    """XML na venda do ML e e-mail ao dono. Falha aqui não desfaz a nota: fica registrada
    em ml_status/email_status e o dono pode repetir pelo painel."""
    xml = (inv.proc_xml or "").encode("utf-8")
    filename = f"NFe{inv.chave}.xml"
    if order.channel == ml.CHANNEL and order.external_id:
        try:
            data = await _ml_order(session, order)
            pack = str(data.get("pack_id") or order.external_id)
            token = await ml.access_token(session)
            await (await ml.client(session)).upload_fiscal_document(token, pack, xml, filename)
            inv.ml_status = f"XML anexado à venda no ML em {datetime.now(BRT):%d/%m %H:%M}"
        except (ml.MLError, MercadoLivreError) as exc:
            inv.ml_status = f"falhou ao anexar no ML: {exc}"
            log.warning("nfe: XML não anexado no ML", extra={"order": order.id})
        await session.commit()

    lines = [
        f"NF-e nº {inv.number} (série {inv.serie}) autorizada — pedido #{order.number}.",
        f"Valor: R$ {inv.total:.2f}".replace(".", ","),
        f"Destinatário: {inv.recipient.get('nome', '')}",
        f"Chave de acesso: {inv.chave}",
    ]
    if inv.ambiente == 2:
        lines.insert(0, "*** HOMOLOGAÇÃO (TESTE): nota sem valor fiscal ***")
    if order.channel == ml.CHANNEL:
        base = await _public_api(session)
        if base:
            link = f"{base}/v1/channels/etiqueta/{label_token(order.id)}"
            lines += ["", "Etiqueta de envio (PDF, vale 30 dias):", link]
        if inv.ml_status:
            lines += ["", inv.ml_status]
    lines += ["", "O XML da nota vai anexo."]
    try:
        to = await mailer.send(
            session,
            subject=f"NF-e nº {inv.number} — pedido #{order.number}",
            text="\n".join(lines),
            attachments=(mailer.Attachment(filename, xml, "application/xml"),),
        )
        inv.email_status = f"enviado para {to} em {datetime.now(BRT):%d/%m %H:%M}"
    except mailer.MailError as exc:
        inv.email_status = str(exc)
    await session.commit()


async def resend(session: AsyncSession, invoice_id: int) -> FiscalInvoice:
    inv = await session.get(FiscalInvoice, invoice_id)
    if inv is None:
        raise FiscalError("nota não existe", status=404)
    if inv.status != "autorizada":
        raise FiscalError("só nota autorizada")
    order = await session.get(Order, inv.order_id)
    assert order is not None
    await after_authorized(session, inv, order)
    return inv


async def list_for_order(session: AsyncSession, order_id: int) -> list[FiscalInvoice]:
    stmt = (
        select(FiscalInvoice)
        .where(FiscalInvoice.order_id == order_id)
        .order_by(FiscalInvoice.id.desc())
    )
    return list((await session.scalars(stmt)).all())
