"""Web services NF-e 4.00 da SEFAZ (SOAP 1.2 com TLS mútuo pelo certificado A1).

Endereços oficiais da SEFAZ-SP (portal.fazenda.sp.gov.br → NF-e → URL dos web services).
Só SP por enquanto: o emitente é paulista.
"""

import re
import secrets
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import httpx

from print3d_fiscal.assinatura import assinar
from print3d_fiscal.certificado import Certificado
from print3d_fiscal.nfe import CUF, NS
from print3d_fiscal.xmlc import el, so_digitos, t

WSDL = "http://www.portalfiscal.inf.br/nfe/wsdl/"
SOAP12 = "http://www.w3.org/2003/05/soap-envelope"

HOSTS = {
    ("SP", 1): "https://nfe.fazenda.sp.gov.br/ws/",
    ("SP", 2): "https://homologacao.nfe.fazenda.sp.gov.br/ws/",
}
# serviço → (arquivo .asmx, nome do serviço no WSDL, operação)
SERVICOS = {
    "status": ("nfestatusservico4.asmx", "NFeStatusServico4", "nfeStatusServicoNF"),
    "autorizacao": ("nfeautorizacao4.asmx", "NFeAutorizacao4", "nfeAutorizacaoLote"),
    "retorno": ("nferetautorizacao4.asmx", "NFeRetAutorizacao4", "nfeRetAutorizacaoLote"),
    "consulta": ("nfeconsultaprotocolo4.asmx", "NFeConsultaProtocolo4", "nfeConsultaNF"),
    "evento": ("nferecepcaoevento4.asmx", "NFeRecepcaoEvento4", "nfeRecepcaoEvento"),
}

AUTORIZADA = {"100", "150"}  # autorizado / autorizado fora do prazo
DENEGADA = {"110", "301", "302", "303"}
EVENTO_OK = {"135", "136", "155"}  # evento registrado (155 = cancelamento fora do prazo)


class SefazError(Exception):
    """Falha de comunicação (rede, TLS, SOAP) — a nota NÃO foi rejeitada pela SEFAZ."""


@dataclass(frozen=True)
class Retorno:
    cstat: str
    motivo: str
    protocolo: str | None = None
    recibo: str | None = None
    prot_xml: str | None = None  # <protNFe> original, para o nfeProc
    evento_xml: str | None = None  # <retEvento> original
    data: str | None = None
    raw: str = ""

    @property
    def autorizada(self) -> bool:
        return self.cstat in AUTORIZADA

    @property
    def denegada(self) -> bool:
        return self.cstat in DENEGADA


class Transmissor(Protocol):
    async def status(self) -> Retorno: ...

    async def autorizar(self, nfe_xml: str) -> Retorno: ...

    async def consultar(self, chave: str) -> Retorno: ...

    async def cancelar(
        self, chave: str, protocolo: str, justificativa: str, quando: datetime
    ) -> Retorno: ...


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _primeiro(raiz: ET.Element, nome: str) -> ET.Element | None:
    for e in raiz.iter():
        if _local(e.tag) == nome:
            return e
    return None


def _texto(raiz: ET.Element | None, nome: str) -> str | None:
    if raiz is None:
        return None
    e = _primeiro(raiz, nome)
    return e.text.strip() if e is not None and e.text else None


def _bruto(texto: str, tag: str) -> str | None:
    """Trecho original do XML (sem re-serializar: preserva a assinatura da SEFAZ)."""
    achado = re.search(rf"<(?:\w+:)?{tag}\b[\s\S]*?</(?:\w+:)?{tag}>", texto)
    return achado.group(0) if achado else None


def nfe_proc(nfe_xml: str, prot_xml: str) -> str:
    """XML de distribuição (o que vai para o cliente e para o Mercado Livre)."""
    corpo = nfe_xml.replace(f'<NFe xmlns="{NS}">', "<NFe>", 1)
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><nfeProc xmlns="{NS}" versao="4.00">'
        f"{corpo}{prot_xml}</nfeProc>"
    )


class Sefaz:
    def __init__(
        self,
        certificado: Certificado,
        *,
        ambiente: int,
        uf: str = "SP",
        timeout: float = 40.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if (uf.upper(), ambiente) not in HOSTS:
            raise SefazError(f"SEFAZ {uf} (ambiente {ambiente}) não atendida")
        cnpj = certificado.cnpj
        if not cnpj:
            raise SefazError("não achei o CNPJ dentro do certificado (precisa ser e-CNPJ A1)")
        self.cert = certificado
        self.cnpj = cnpj
        self.ambiente = ambiente
        self.uf = uf.upper()
        self.cuf = CUF[self.uf]
        self._timeout = timeout
        self._transport = transport

    def _cliente(self) -> httpx.AsyncClient:
        if self._transport is not None:
            return httpx.AsyncClient(transport=self._transport, timeout=self._timeout)
        return httpx.AsyncClient(verify=self.cert.contexto_tls(), timeout=self._timeout)

    async def _chamar(self, servico: str, dados: str) -> tuple[str, ET.Element]:
        arquivo, nome, operacao = SERVICOS[servico]
        envelope = (
            f'<?xml version="1.0" encoding="utf-8"?><soap12:Envelope xmlns:soap12="{SOAP12}">'
            f'<soap12:Body><nfeDadosMsg xmlns="{WSDL}{nome}">{dados}</nfeDadosMsg>'
            "</soap12:Body></soap12:Envelope>"
        )
        cabecalho = {
            "Content-Type": (
                f'application/soap+xml; charset=utf-8; action="{WSDL}{nome}/{operacao}"'
            )
        }
        url = HOSTS[(self.uf, self.ambiente)] + arquivo
        try:
            async with self._cliente() as http:
                res = await http.post(url, content=envelope.encode("utf-8"), headers=cabecalho)
        except httpx.HTTPError as exc:
            raise SefazError(f"sem resposta da SEFAZ ({type(exc).__name__}: {exc})") from exc
        texto = res.text
        try:
            # resposta da SEFAZ por TLS verificado (raiz ICP-Brasil); não é entrada de usuário
            raiz = ET.fromstring(texto)  # noqa: S314
        except ET.ParseError as exc:
            raise SefazError(f"SEFAZ respondeu HTTP {res.status_code} sem XML válido") from exc
        if _primeiro(raiz, "Fault") is not None:
            motivo = _texto(raiz, "Text") or _texto(raiz, "Reason") or "erro SOAP"
            raise SefazError(f"SEFAZ recusou a chamada: {motivo}")
        resultado = _primeiro(raiz, "nfeResultMsg")
        if resultado is None:
            raise SefazError(f"SEFAZ respondeu HTTP {res.status_code} sem resultado")
        return texto, resultado

    async def status(self) -> Retorno:
        dados = el(
            "consStatServ",
            t("tpAmb", str(self.ambiente)),
            t("cUF", self.cuf),
            t("xServ", "STATUS"),
            attrs={"versao": "4.00"},
            ns=NS,
        )
        texto, r = await self._chamar("status", dados)
        return Retorno(
            cstat=_texto(r, "cStat") or "",
            motivo=_texto(r, "xMotivo") or "",
            data=_texto(r, "dhRecbto"),
            raw=texto,
        )

    async def autorizar(self, nfe_xml: str) -> Retorno:
        lote = f"{secrets.randbelow(10**15):015d}"
        dados = (
            f'<enviNFe xmlns="{NS}" versao="4.00"><idLote>{lote}</idLote>'
            f"<indSinc>1</indSinc>{nfe_xml}</enviNFe>"
        )
        texto, r = await self._chamar("autorizacao", dados)
        cstat = _texto(r, "cStat") or ""
        if cstat == "103":  # lote recebido para processamento assíncrono: busca o recibo
            recibo = _texto(r, "nRec")
            if not recibo:
                raise SefazError("SEFAZ recebeu o lote mas não devolveu o recibo")
            return await self.retorno(recibo)
        return self._resultado_nota(texto, r)

    async def retorno(self, recibo: str) -> Retorno:
        dados = el(
            "consReciNFe",
            t("tpAmb", str(self.ambiente)),
            t("nRec", so_digitos(recibo)),
            attrs={"versao": "4.00"},
            ns=NS,
        )
        texto, r = await self._chamar("retorno", dados)
        if (_texto(r, "cStat") or "") == "105":  # ainda processando
            return Retorno(cstat="105", motivo="Lote em processamento", recibo=recibo, raw=texto)
        resultado = self._resultado_nota(texto, r)
        return Retorno(**{**resultado.__dict__, "recibo": recibo})

    @staticmethod
    def _resultado_nota(texto: str, r: ET.Element) -> Retorno:
        prot = _primeiro(r, "protNFe")
        if prot is not None:  # resultado da nota (e não só do lote)
            return Retorno(
                cstat=_texto(prot, "cStat") or "",
                motivo=_texto(prot, "xMotivo") or "",
                protocolo=_texto(prot, "nProt"),
                prot_xml=_bruto(texto, "protNFe"),
                data=_texto(prot, "dhRecbto"),
                raw=texto,
            )
        return Retorno(cstat=_texto(r, "cStat") or "", motivo=_texto(r, "xMotivo") or "", raw=texto)

    async def consultar(self, chave: str) -> Retorno:
        dados = el(
            "consSitNFe",
            t("tpAmb", str(self.ambiente)),
            t("xServ", "CONSULTAR"),
            t("chNFe", so_digitos(chave)),
            attrs={"versao": "4.00"},
            ns=NS,
        )
        texto, r = await self._chamar("consulta", dados)
        return self._resultado_nota(texto, r)

    async def cancelar(
        self, chave: str, protocolo: str, justificativa: str, quando: datetime
    ) -> Retorno:
        justificativa = justificativa.strip()
        if not 15 <= len(justificativa) <= 255:
            raise ValueError("a justificativa do cancelamento precisa de 15 a 255 caracteres")
        if quando.tzinfo is None:
            raise ValueError("data do evento sem fuso horário")
        chave = so_digitos(chave)
        id_evento = f"ID110111{chave}01"
        filhos = (
            t("cOrgao", self.cuf),
            t("tpAmb", str(self.ambiente)),
            t("CNPJ", self.cnpj),
            t("chNFe", chave),
            t("dhEvento", quando.isoformat(timespec="seconds")),
            t("tpEvento", "110111"),
            t("nSeqEvento", "1"),
            t("verEvento", "1.00"),
            el(
                "detEvento",
                t("descEvento", "Cancelamento"),
                t("nProt", so_digitos(protocolo)),
                t("xJust", justificativa, limite=255),
                attrs={"versao": "1.00"},
            ),
        )
        attrs = {"Id": id_evento}
        assinatura = assinar(el("infEvento", *filhos, attrs=attrs, ns=NS), id_evento, self.cert)
        evento = el(
            "evento", el("infEvento", *filhos, attrs=attrs), assinatura, attrs={"versao": "1.00"}
        )
        lote = f"{secrets.randbelow(10**15):015d}"
        dados = el(
            "envEvento",
            t("idLote", lote),
            evento,
            attrs={"versao": "1.00"},
            ns=NS,
        )
        texto, r = await self._chamar("evento", dados)
        ret = _primeiro(r, "retEvento")
        if ret is None:
            return Retorno(
                cstat=_texto(r, "cStat") or "", motivo=_texto(r, "xMotivo") or "", raw=texto
            )
        return Retorno(
            cstat=_texto(ret, "cStat") or "",
            motivo=_texto(ret, "xMotivo") or "",
            protocolo=_texto(ret, "nProt"),
            evento_xml=_bruto(texto, "retEvento"),
            data=_texto(ret, "dhRegEvento"),
            raw=texto,
        )
