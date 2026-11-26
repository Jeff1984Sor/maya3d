"""Montagem da NF-e modelo 55, leiaute 4.00 (MOC 7.0), para venda de produção própria por
emitente do Simples Nacional/MEI (ICMS por CSOSN). Sem grupo IBS/CBS: para CRT 1, 2 e 4 ele
só é exigido a partir de 04/01/2027 (NT 2025.002).

Nenhum dado da empresa fica aqui: tudo chega pelos dataclasses (o painel configura).
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from print3d_fiscal.assinatura import Assinador, assinar
from print3d_fiscal.chave import Chave, codigo_numerico
from print3d_fiscal.xmlc import dec, el, so_digitos, t

NS = "http://www.portalfiscal.inf.br/nfe"
VERSAO = "4.00"
CUF = {"SP": "35"}  # UFs atendidas (web services em sefaz.py)
DEST_HOMOLOGACAO = "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL"
SEM_GTIN = "SEM GTIN"


class NotaError(ValueError):
    pass


@dataclass(frozen=True)
class Endereco:
    logradouro: str
    numero: str
    bairro: str
    cod_municipio: str  # IBGE, 7 dígitos
    municipio: str
    uf: str
    cep: str
    complemento: str | None = None
    fone: str | None = None


@dataclass(frozen=True)
class Emitente:
    cnpj: str
    razao_social: str
    ie: str
    crt: int  # 1 Simples, 2 Simples excesso, 3 normal, 4 MEI
    endereco: Endereco
    nome_fantasia: str | None = None


@dataclass(frozen=True)
class Destinatario:
    nome: str
    documento: str  # CPF (11) ou CNPJ (14)
    endereco: Endereco
    email: str | None = None
    ie: str | None = None  # só PJ contribuinte


@dataclass(frozen=True)
class Item:
    codigo: str
    descricao: str
    ncm: str
    cfop: str
    quantidade: Decimal
    valor_unitario: Decimal
    unidade: str = "UN"
    origem: int = 0
    csosn: str = "102"
    gtin: str | None = None

    @property
    def valor_bruto(self) -> Decimal:
        return (self.quantidade * self.valor_unitario).quantize(Decimal("0.01"))


@dataclass(frozen=True)
class Pagamento:
    tipo: str  # tPag: 01 dinheiro, 03 crédito, 04 débito, 17 Pix, 99 outros...
    valor: Decimal
    descricao: str | None = None  # obrigatório com tipo 99


@dataclass(frozen=True)
class Intermediador:
    """Marketplace (ex.: Mercado Livre) — NT 2020.006."""

    cnpj: str
    id_cadastro: str  # identificação do vendedor no marketplace


@dataclass(frozen=True)
class RespTecnico:
    cnpj: str
    contato: str
    email: str
    fone: str


# Alíquota interestadual (Res. Senado 22/1989 e 13/2012): Sul/Sudeste (menos ES) → N/NE/CO/ES
# = 7%; demais = 12%; mercadoria importada (origem 1, 2, 3, 8) = 4%.
SUL_SUDESTE = {"SP", "RJ", "MG", "PR", "SC", "RS"}
ORIGEM_IMPORTADA = {1, 2, 3, 8}


def aliquota_interestadual(uf_origem: str, uf_destino: str, origem: int = 0) -> Decimal:
    if origem in ORIGEM_IMPORTADA:
        return Decimal(4)
    if uf_origem.upper() in SUL_SUDESTE and uf_destino.upper() not in SUL_SUDESTE:
        return Decimal(7)
    return Decimal(12)


@dataclass(frozen=True)
class Difal:
    """Venda a consumidor final não contribuinte de outro estado (EC 87/2015): grupo
    ICMSUFDest. A alíquota interna do destino (e o FCP) vem da configuração."""

    aliquota_interna: Decimal  # do estado de destino, em %
    aliquota_fcp: Decimal = Decimal(0)


@dataclass(frozen=True)
class Nota:
    emitente: Emitente
    destinatario: Destinatario
    itens: tuple[Item, ...]
    numero: int
    serie: int
    emissao: datetime  # com fuso
    ambiente: int  # 1 produção, 2 homologação
    natureza: str = "Venda de mercadoria"  # MEI (CRT 4) só pode CFOP 5102/6102
    mod_frete: int = 0  # 0 remetente (CIF), 1 destinatário (FOB), 9 sem frete
    frete: Decimal = Decimal(0)
    desconto: Decimal = Decimal(0)
    pagamentos: tuple[Pagamento, ...] = ()
    intermediador: Intermediador | None = None
    info_complementar: str | None = None
    resp_tecnico: RespTecnico | None = None
    consumidor_final: bool = True
    presenca: int = 2  # 2 = internet
    ver_proc: str = "print3d-fiscal 1.0"
    codigo_numerico: str | None = None
    difal: Difal | None = None


@dataclass(frozen=True)
class NotaMontada:
    chave: str
    xml: str  # <NFe> assinada, pronta para o lote
    valor_total: Decimal


def _grupo_csosn(csosn: str) -> str:
    if csosn in ("102", "103", "300", "400"):
        return "ICMSSN102"
    if csosn in ("101", "201", "202", "500", "900"):
        raise NotaError(f"CSOSN {csosn} exige campos de crédito/ST que este emissor não faz")
    raise NotaError(f"CSOSN inválido: {csosn}")


def _ratear(total: Decimal, bases: list[Decimal]) -> list[Decimal]:
    """Divide `total` proporcional às bases; a última recebe a sobra dos centavos."""
    if total <= 0:
        return [Decimal(0)] * len(bases)
    soma = sum(bases) or Decimal(1)
    partes = [(total * b / soma).quantize(Decimal("0.01")) for b in bases[:-1]]
    return [*partes, total - sum(partes, Decimal(0))]


def _documento(doc: str) -> str:
    digitos = so_digitos(doc)
    if len(digitos) == 11:
        return t("CPF", digitos) or ""
    if len(digitos) == 14:
        return t("CNPJ", digitos) or ""
    raise NotaError("CPF/CNPJ do destinatário inválido")


def _endereco(tag: str, e: Endereco, *, cep_obrigatorio: bool = True) -> str:
    cep = so_digitos(e.cep)
    if len(so_digitos(e.cod_municipio)) != 7:
        raise NotaError(f"código IBGE do município inválido ({e.municipio})")
    if cep_obrigatorio and len(cep) != 8:
        raise NotaError(f"CEP inválido ({e.municipio})")
    fone = so_digitos(e.fone)
    return el(
        tag,
        t("xLgr", e.logradouro, limite=60),
        t("nro", e.numero or "S/N", limite=60),
        t("xCpl", e.complemento, limite=60),
        t("xBairro", e.bairro, limite=60),
        t("cMun", so_digitos(e.cod_municipio)),
        t("xMun", e.municipio, limite=60),
        t("UF", e.uf.upper()),
        t("CEP", cep or None),
        t("cPais", "1058"),
        t("xPais", "Brasil"),
        t("fone", fone if 6 <= len(fone) <= 14 else None),
    )


def _validar(n: Nota) -> None:
    if not n.itens:
        raise NotaError("nota sem itens")
    if n.emitente.endereco.uf.upper() not in CUF:
        raise NotaError(f"UF do emitente não atendida: {n.emitente.endereco.uf}")
    if n.ambiente not in (1, 2):
        raise NotaError("ambiente deve ser 1 (produção) ou 2 (homologação)")
    if not 1 <= n.numero <= 999_999_999 or not 0 <= n.serie <= 999:
        raise NotaError("número/série da nota fora da faixa")
    if n.emissao.tzinfo is None:
        raise NotaError("data de emissão sem fuso horário")
    for i in n.itens:
        if len(so_digitos(i.ncm)) != 8:
            raise NotaError(f"NCM inválido no item {i.descricao!r}")
        if len(so_digitos(i.cfop)) != 4:
            raise NotaError(f"CFOP inválido no item {i.descricao!r}")
        if i.quantidade <= 0 or i.valor_unitario <= 0:
            raise NotaError(f"quantidade/valor inválido no item {i.descricao!r}")


def montar(n: Nota, assinador: Assinador) -> NotaMontada:
    _validar(n)
    emit, dest = n.emitente, n.destinatario
    cuf = CUF[emit.endereco.uf.upper()]
    cnf = n.codigo_numerico or codigo_numerico(n.numero)
    chave = Chave(cuf, n.emissao, so_digitos(emit.cnpj), 55, n.serie, n.numero, 1, cnf)
    id_nfe = f"NFe{chave.valor}"
    interna = dest.endereco.uf.upper() == emit.endereco.uf.upper()

    brutos = [i.valor_bruto for i in n.itens]
    fretes = _ratear(n.frete, brutos)
    descontos = _ratear(n.desconto, brutos)
    v_prod = sum(brutos, Decimal(0))
    v_nf = v_prod - n.desconto + n.frete
    if v_nf <= 0:
        raise NotaError("valor total da nota precisa ser positivo")

    ide = el(
        "ide",
        t("cUF", cuf),
        t("cNF", cnf),
        t("natOp", n.natureza, limite=60),
        t("mod", "55"),
        t("serie", str(n.serie)),
        t("nNF", str(n.numero)),
        t("dhEmi", n.emissao.isoformat(timespec="seconds")),
        t("tpNF", "1"),
        t("idDest", "1" if interna else "2"),
        t("cMunFG", so_digitos(emit.endereco.cod_municipio)),
        t("tpImp", "1"),
        t("tpEmis", "1"),
        t("cDV", str(chave.dv)),
        t("tpAmb", str(n.ambiente)),
        t("finNFe", "1"),
        t("indFinal", "1" if n.consumidor_final else "0"),
        t("indPres", str(n.presenca)),
        t("indIntermed", "1" if n.intermediador else "0"),
        t("procEmi", "0"),
        t("verProc", n.ver_proc, limite=20),
    )
    e = emit
    emit_xml = el(
        "emit",
        t("CNPJ", so_digitos(e.cnpj)),
        t("xNome", e.razao_social, limite=60),
        t("xFant", e.nome_fantasia, limite=60),
        _endereco("enderEmit", e.endereco),
        t("IE", so_digitos(e.ie)),
        t("CRT", str(e.crt)),
    )
    ie_dest = so_digitos(dest.ie)
    dest_xml = el(
        "dest",
        _documento(dest.documento),
        t("xNome", DEST_HOMOLOGACAO if n.ambiente == 2 else dest.nome, limite=60),
        _endereco("enderDest", dest.endereco),
        t("indIEDest", "1" if ie_dest else "9"),
        t("IE", ie_dest or None),
        t("email", dest.email, limite=60),
    )
    # DIFAL só existe em venda interestadual a consumidor final não contribuinte
    usa_difal = (
        n.difal is not None and not interna and n.consumidor_final and not so_digitos(dest.ie)
    )
    difal_tot = [Decimal(0), Decimal(0)]  # FCP, ICMS do destino
    dets = []
    for num, (item, v_frete, v_desc) in enumerate(
        zip(n.itens, fretes, descontos, strict=True), start=1
    ):
        gtin = so_digitos(item.gtin) or SEM_GTIN
        prod = el(
            "prod",
            t("cProd", item.codigo, limite=60),
            t("cEAN", gtin),
            t("xProd", item.descricao, limite=120),
            t("NCM", so_digitos(item.ncm)),
            t("CFOP", so_digitos(item.cfop)),
            t("uCom", item.unidade, limite=6),
            t("qCom", dec(item.quantidade, 4)),
            t("vUnCom", dec(item.valor_unitario, 2)),
            t("vProd", dec(item.valor_bruto)),
            t("cEANTrib", gtin),
            t("uTrib", item.unidade, limite=6),
            t("qTrib", dec(item.quantidade, 4)),
            t("vUnTrib", dec(item.valor_unitario, 2)),
            t("vFrete", dec(v_frete) if v_frete > 0 else None),
            t("vDesc", dec(v_desc) if v_desc > 0 else None),
            t("indTot", "1"),
        )
        imposto = el(
            "imposto",
            el(
                "ICMS",
                el(
                    _grupo_csosn(item.csosn),
                    t("orig", str(item.origem)),
                    t("CSOSN", item.csosn),
                ),
            ),
            # Simples Nacional: PIS/COFINS recolhidos no DAS — CST 99 zerado na nota.
            el(
                "PIS",
                el(
                    "PISOutr",
                    t("CST", "99"),
                    t("vBC", "0.00"),
                    t("pPIS", "0.0000"),
                    t("vPIS", "0.00"),
                ),
            ),
            el(
                "COFINS",
                el(
                    "COFINSOutr",
                    t("CST", "99"),
                    t("vBC", "0.00"),
                    t("pCOFINS", "0.0000"),
                    t("vCOFINS", "0.00"),
                ),
            ),
        )
        if usa_difal and n.difal is not None:
            base = item.valor_bruto - v_desc + v_frete
            inter = aliquota_interestadual(emit.endereco.uf, dest.endereco.uf, item.origem)
            v_icms_dest = (base * max(n.difal.aliquota_interna - inter, Decimal(0)) / 100).quantize(
                Decimal("0.01")
            )
            v_fcp = (base * n.difal.aliquota_fcp / 100).quantize(Decimal("0.01"))
            difal_tot[0] += v_fcp
            difal_tot[1] += v_icms_dest
            grupo = el(
                "ICMSUFDest",
                t("vBCUFDest", dec(base)),
                t("vBCFCPUFDest", dec(base) if n.difal.aliquota_fcp > 0 else None),
                t("pFCPUFDest", dec(n.difal.aliquota_fcp, 4)),
                t("pICMSUFDest", dec(n.difal.aliquota_interna, 4)),
                t("pICMSInter", dec(inter, 2)),
                t("pICMSInterPart", "100.0000"),
                t("vFCPUFDest", dec(v_fcp)),
                t("vICMSUFDest", dec(v_icms_dest)),
                t("vICMSUFRemet", "0.00"),
            )
            imposto = imposto.replace("</imposto>", grupo + "</imposto>")
        dets.append(el("det", prod, imposto, attrs={"nItem": str(num)}))

    zero = "0.00"
    total = el(
        "total",
        el(
            "ICMSTot",
            t("vBC", zero),
            t("vICMS", zero),
            t("vICMSDeson", zero),
            t("vFCPUFDest", dec(difal_tot[0]) if usa_difal else None),
            t("vICMSUFDest", dec(difal_tot[1]) if usa_difal else None),
            t("vICMSUFRemet", zero if usa_difal else None),
            t("vFCP", zero),
            t("vBCST", zero),
            t("vST", zero),
            t("vFCPST", zero),
            t("vFCPSTRet", zero),
            t("vProd", dec(v_prod)),
            t("vFrete", dec(n.frete)),
            t("vSeg", zero),
            t("vDesc", dec(n.desconto)),
            t("vII", zero),
            t("vIPI", zero),
            t("vIPIDevol", zero),
            t("vPIS", zero),
            t("vCOFINS", zero),
            t("vOutro", zero),
            t("vNF", dec(v_nf)),
        ),
    )
    transp = el("transp", t("modFrete", str(n.mod_frete)))
    pagamentos = n.pagamentos or (Pagamento("99", v_nf, "Outros"),)
    pag = el(
        "pag",
        *[
            el(
                "detPag",
                t("indPag", "0"),
                t("tPag", p.tipo),
                t("xPag", (p.descricao or "Outros") if p.tipo == "99" else None, limite=60),
                t("vPag", dec(p.valor)),
                # cartão sem integração com a maquininha (tpIntegra 2)
                el("card", t("tpIntegra", "2")) if p.tipo in ("03", "04") else None,
            )
            for p in pagamentos
        ],
    )
    intermed = (
        el(
            "infIntermed",
            t("CNPJ", so_digitos(n.intermediador.cnpj)),
            t("idCadIntTran", n.intermediador.id_cadastro, limite=60),
        )
        if n.intermediador
        else None
    )
    info = None
    if n.info_complementar:
        info = el("infAdic", t("infCpl", n.info_complementar, limite=5000))
    rt = n.resp_tecnico
    resp = (
        el(
            "infRespTec",
            t("CNPJ", so_digitos(rt.cnpj)),
            t("xContato", rt.contato, limite=60),
            t("email", rt.email, limite=60),
            t("fone", so_digitos(rt.fone)),
        )
        if rt
        else None
    )
    filhos = (ide, emit_xml, dest_xml, *dets, total, transp, pag, intermed, info, resp)
    attrs = {"Id": id_nfe, "versao": VERSAO}
    canonico = el("infNFe", *filhos, attrs=attrs, ns=NS)
    inf = el("infNFe", *filhos, attrs=attrs)
    assinatura = assinar(canonico, id_nfe, assinador)
    return NotaMontada(chave=chave.valor, xml=el("NFe", inf, assinatura, ns=NS), valor_total=v_nf)
