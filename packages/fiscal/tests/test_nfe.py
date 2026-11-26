import base64
import hashlib
import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from print3d_fiscal import (
    CertificadoError,
    Destinatario,
    Difal,
    Emitente,
    Endereco,
    Intermediador,
    Item,
    Nota,
    NotaError,
    Pagamento,
    Sefaz,
    carregar_pfx_base64,
    gerar_danfe,
    montar,
    nfe_proc,
)
from print3d_fiscal.certificado import OID_CNPJ
from print3d_fiscal.chave import dv_mod11
from print3d_fiscal.xmlc import limpar

CNPJ = "11222333000181"
BRT = timezone(timedelta(hours=-3))
NS = "http://www.portalfiscal.inf.br/nfe"
DSIG = "http://www.w3.org/2000/09/xmldsig#"


@pytest.fixture(scope="module")
def pfx_b64() -> str:
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"EMPRESA TESTE:{CNPJ}")])
    agora = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - timedelta(days=1))
        .not_valid_after(agora + timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([x509.OtherName(OID_CNPJ, b"\x04\x0e" + CNPJ.encode())]),
            critical=False,
        )
        .sign(chave, hashes.SHA256())
    )
    dados = pkcs12.serialize_key_and_certificates(
        b"teste", chave, cert, None, serialization.BestAvailableEncryption(b"senha123")
    )
    return base64.b64encode(dados).decode()


def _endereco(uf: str = "SP") -> Endereco:
    return Endereco(
        logradouro="Rua das Flores",
        numero="10",
        bairro="Centro",
        cod_municipio="3552205" if uf == "SP" else "3106705",
        municipio="Sorocaba" if uf == "SP" else "Betim",
        uf=uf,
        cep="18081000" if uf == "SP" else "32600000",
    )


def _nota(ambiente: int = 1, uf_dest: str = "MG", **extra: object) -> Nota:
    base: dict[str, object] = {
        "emitente": Emitente(
            cnpj=CNPJ,
            razao_social="Empresa Teste \u2013 MEI",
            ie="151854851113",
            crt=4,
            endereco=_endereco("SP"),
            nome_fantasia="Loja",
        ),
        "destinatario": Destinatario(
            nome="Maria  da Silva", documento="123.456.789-09", endereco=_endereco(uf_dest)
        ),
        "itens": (
            Item(
                codigo="V12",
                descricao="Imagem de Nossa Senhora em Oração",
                ncm="3926.40.00",
                cfop="6107",
                quantidade=Decimal(2),
                valor_unitario=Decimal("25.90"),
            ),
            Item(
                codigo="V13",
                descricao="Chaveiro <coração> & cia",
                ncm="39264000",
                cfop="6107",
                quantidade=Decimal(1),
                valor_unitario=Decimal("10.00"),
            ),
        ),
        "numero": 1,
        "serie": 1,
        "emissao": datetime(2026, 11, 26, 10, 30, tzinfo=BRT),
        "ambiente": ambiente,
        "frete": Decimal("11.99"),
        "desconto": Decimal("1.00"),
        "pagamentos": (Pagamento("99", Decimal("72.79"), "Mercado Pago"),),
        "intermediador": Intermediador("03007331000141", "LOJA"),
        "info_complementar": "Documento emitido por ME ou EPP optante pelo Simples Nacional.",
        "codigo_numerico": "12345678",
    }
    base.update(extra)
    return Nota(**base)  # type: ignore[arg-type]


def _local(e: ET.Element) -> str:
    return e.tag.rsplit("}", 1)[-1]


def _achar(raiz: ET.Element, nome: str) -> ET.Element:
    for e in raiz.iter():
        if _local(e) == nome:
            return e
    raise AssertionError(nome)


def test_dv_exemplo_do_manual() -> None:
    assert dv_mod11("5206043300991100250655012000000780026730161") == 5


def test_limpar_texto_para_o_schema() -> None:
    assert limpar("  Peça \u2013  \u201c3D\u201d\u2026\n ok ") == 'Peça - "3D"... ok'
    assert limpar("emoji 😀 fora") == "emoji fora"


def test_certificado_a1(pfx_b64: str) -> None:
    cert = carregar_pfx_base64(pfx_b64, "senha123")
    assert cert.cnpj == CNPJ
    assert not cert.vencido()
    with pytest.raises(CertificadoError):
        carregar_pfx_base64(pfx_b64, "errada")


def test_monta_e_assina_nfe(pfx_b64: str) -> None:
    cert = carregar_pfx_base64(pfx_b64, "senha123")
    nota = montar(_nota(), cert)
    assert len(nota.chave) == 44
    assert nota.chave[20:22] == "55"
    assert nota.chave.startswith("352611" + CNPJ)
    assert dv_mod11(nota.chave[:43]) == int(nota.chave[43])
    # 2 x 25,90 + 10,00 = 61,80; menos 1,00 de desconto; mais 11,99 de frete = 72,79
    assert nota.valor_total == Decimal("72.79")

    raiz = ET.fromstring(nota.xml)  # noqa: S314
    assert _achar(raiz, "idDest").text == "2"
    assert _achar(raiz, "indIntermed").text == "1"
    assert _achar(raiz, "xNome").text == "Empresa Teste - MEI"  # travessão trocado
    fretes = [e.text for e in raiz.iter() if _local(e) == "vFrete"]
    assert fretes[:2] == ["10.05", "1.94"]  # rateio fecha
    assert fretes[-1] == "11.99"
    assert _achar(raiz, "vNF").text == "72.79"
    assert _achar(raiz, "xProd").text == "Imagem de Nossa Senhora em Oração"

    # Assinatura: o digest bate com a C14N independente (xml.etree) do infNFe...
    inf = re.search(r"<infNFe [\s\S]*</infNFe>", nota.xml)
    assert inf
    standalone = inf.group(0).replace("<infNFe ", f'<infNFe xmlns="{NS}" ', 1)
    canon = ET.canonicalize(standalone)
    assert canon == standalone
    digest = base64.b64encode(hashlib.sha1(canon.encode()).digest()).decode()  # noqa: S324
    assert _achar(raiz, "DigestValue").text == digest
    assert _achar(raiz, "Reference").get("URI") == f"#NFe{nota.chave}"

    # ...e a SignatureValue confere com a chave pública sobre o SignedInfo canônico.
    si = re.search(r"<SignedInfo>[\s\S]*</SignedInfo>", nota.xml)
    assert si
    si_canon = ET.canonicalize(si.group(0).replace("<SignedInfo>", f'<SignedInfo xmlns="{DSIG}">'))
    assinatura = base64.b64decode(_achar(raiz, "SignatureValue").text or "")
    cert.cert.public_key().verify(  # type: ignore[union-attr,call-arg]
        assinatura,
        si_canon.encode(),
        padding.PKCS1v15(),  # type: ignore[arg-type]
        hashes.SHA1(),  # noqa: S303
    )


def test_homologacao_troca_nome_do_destinatario(pfx_b64: str) -> None:
    cert = carregar_pfx_base64(pfx_b64, "senha123")
    nota = montar(_nota(ambiente=2, uf_dest="SP"), cert)
    raiz = ET.fromstring(nota.xml)  # noqa: S314
    dest = _achar(raiz, "dest")
    assert _achar(dest, "xNome").text == (
        "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO - SEM VALOR FISCAL"
    )
    assert _achar(raiz, "idDest").text == "1"
    assert _achar(raiz, "tpAmb").text == "2"


def test_validacoes(pfx_b64: str) -> None:
    cert = carregar_pfx_base64(pfx_b64, "senha123")
    ruim = Item("X", "Peça", "123", "5101", Decimal(1), Decimal(1))
    with pytest.raises(NotaError, match="NCM"):
        montar(_nota(itens=(ruim,)), cert)
    with pytest.raises(NotaError, match="fuso"):
        montar(_nota(emissao=datetime(2026, 11, 26)), cert)


RESPOSTA = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"><soap:Body>
<nfeResultMsg xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeAutorizacao4">
<retEnviNFe versao="4.00" xmlns="http://www.portalfiscal.inf.br/nfe"><tpAmb>2</tpAmb>
<cStat>104</cStat><xMotivo>Lote processado</xMotivo>
<protNFe versao="4.00"><infProt><tpAmb>2</tpAmb><chNFe>{chave}</chNFe>
<dhRecbto>2026-11-26T10:31:00-03:00</dhRecbto><nProt>135260000000001</nProt>
<cStat>100</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo></infProt></protNFe>
</retEnviNFe></nfeResultMsg></soap:Body></soap:Envelope>"""


async def test_autoriza_na_sefaz(pfx_b64: str) -> None:
    cert = carregar_pfx_base64(pfx_b64, "senha123")
    nota = montar(_nota(ambiente=2), cert)
    pedidos: list[httpx.Request] = []

    def responder(req: httpx.Request) -> httpx.Response:
        pedidos.append(req)
        return httpx.Response(200, text=RESPOSTA.format(chave=nota.chave))

    sefaz = Sefaz(cert, ambiente=2, transport=httpx.MockTransport(responder))
    ret = await sefaz.autorizar(nota.xml)
    assert ret.autorizada
    assert ret.protocolo == "135260000000001"
    assert ret.prot_xml
    assert ret.prot_xml.startswith("<protNFe")
    req = pedidos[0]
    assert str(req.url) == "https://homologacao.nfe.fazenda.sp.gov.br/ws/nfeautorizacao4.asmx"
    assert "nfeAutorizacaoLote" in req.headers["content-type"]
    assert "<indSinc>1</indSinc>" in req.content.decode()

    proc = nfe_proc(nota.xml, ret.prot_xml)
    raiz = ET.fromstring(proc.split("?>", 1)[1])  # noqa: S314
    assert _local(raiz) == "nfeProc"
    assert _achar(raiz, "nProt").text == "135260000000001"


async def test_falha_de_rede_nao_vira_rejeicao(pfx_b64: str) -> None:
    cert = carregar_pfx_base64(pfx_b64, "senha123")

    def cair(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("tempo esgotado", request=req)

    from print3d_fiscal import SefazError

    sefaz = Sefaz(cert, ambiente=2, transport=httpx.MockTransport(cair))
    with pytest.raises(SefazError, match="sem resposta"):
        await sefaz.status()


async def test_cancelamento_assinado(pfx_b64: str) -> None:
    cert = carregar_pfx_base64(pfx_b64, "senha123")
    enviados: list[str] = []

    def responder(req: httpx.Request) -> httpx.Response:
        enviados.append(req.content.decode())
        return httpx.Response(
            200,
            text=(
                '<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"><soap:Body>'
                '<nfeResultMsg xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeRecepcaoEvento4">'
                '<retEnvEvento xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.00">'
                "<cStat>128</cStat><xMotivo>Lote de evento processado</xMotivo>"
                '<retEvento versao="1.00"><infEvento><cStat>135</cStat>'
                "<xMotivo>Evento registrado e vinculado a NF-e</xMotivo>"
                "<nProt>135260000000002</nProt></infEvento></retEvento>"
                "</retEnvEvento></nfeResultMsg></soap:Body></soap:Envelope>"
            ),
        )

    sefaz = Sefaz(cert, ambiente=2, transport=httpx.MockTransport(responder))
    with pytest.raises(ValueError, match="15 a 255"):
        await sefaz.cancelar("3" * 44, "1", "curta", datetime.now(BRT))
    ret = await sefaz.cancelar(
        "3" * 44, "135260000000001", "Venda cancelada pelo comprador", datetime.now(BRT)
    )
    assert ret.cstat == "135"
    assert ret.protocolo == "135260000000002"
    assert f'Id="ID110111{"3" * 44}01"' in enviados[0]
    assert "<Signature " in enviados[0]


def test_difal_interestadual(pfx_b64: str) -> None:
    cert = carregar_pfx_base64(pfx_b64, "senha123")
    nota = montar(_nota(difal=Difal(Decimal(18), Decimal(2))), cert)
    raiz = ET.fromstring(nota.xml)  # noqa: S314
    grupos = [e for e in raiz.iter() if _local(e) == "ICMSUFDest"]
    assert len(grupos) == 2
    # item 1: 51,80 - 0,84 de desconto + 10,05 de frete = 61,01; SP→MG = 12%; 18 - 12 = 6%
    g = grupos[0]
    assert _achar(g, "vBCUFDest").text == "61.01"
    assert _achar(g, "pICMSInter").text == "12.00"
    assert _achar(g, "vICMSUFDest").text == "3.66"
    assert _achar(g, "vFCPUFDest").text == "1.22"
    tot = _achar(raiz, "ICMSTot")
    nomes = [_local(e) for e in tot]
    assert nomes[2:6] == ["vICMSDeson", "vFCPUFDest", "vICMSUFDest", "vICMSUFRemet"]
    # dentro do imposto, o grupo vem depois de COFINS
    imposto = _achar(raiz, "imposto")
    assert [_local(e) for e in imposto][-1] == "ICMSUFDest"
    # venda no mesmo estado não leva DIFAL
    interna = montar(_nota(uf_dest="SP", difal=Difal(Decimal(18))), cert)
    assert "ICMSUFDest" not in interna.xml


def test_danfe_pdf(pfx_b64: str) -> None:
    cert = carregar_pfx_base64(pfx_b64, "senha123")
    nota = montar(_nota(), cert)
    prot = (
        '<protNFe versao="4.00"><infProt><nProt>135260000000001</nProt>'
        "<dhRecbto>2026-11-26T10:31:00-03:00</dhRecbto><cStat>100</cStat></infProt></protNFe>"
    )
    pdf = gerar_danfe(nfe_proc(nota.xml, prot))
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 3000
    assert gerar_danfe(nfe_proc(nota.xml, prot), cancelada=True).startswith(b"%PDF")
