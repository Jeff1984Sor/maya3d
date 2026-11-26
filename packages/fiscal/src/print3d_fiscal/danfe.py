"""DANFE (retrato, A4) gerado do XML autorizado (nfeProc) — sem serviço externo.

Segue os blocos do Manual de Orientação (anexo II): canhoto, identificação do emitente,
chave com código de barras CODE-128C, protocolo, destinatário, cálculo do imposto,
transportador, produtos e dados adicionais. Homologação e nota cancelada levam marca d'água.
"""

import io
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

from reportlab.graphics.barcode.code128 import Code128
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

W, H = A4
M = 6 * mm  # margem
LARGURA = W - 2 * M
MOD_FRETE = {
    "0": "0 - Remetente (CIF)",
    "1": "1 - Destinatário (FOB)",
    "2": "2 - Terceiros",
    "3": "3 - Próprio remetente",
    "4": "4 - Próprio destinatário",
    "9": "9 - Sem frete",
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find(raiz: ET.Element | None, caminho: str) -> ET.Element | None:
    """Busca por caminho de nomes locais (ignora namespace): 'emit/enderEmit/xMun'."""
    atual = raiz
    for parte in caminho.split("/"):
        if atual is None:
            return None
        atual = next((c for c in atual if _local(c.tag) == parte), None)
    return atual


def _t(raiz: ET.Element | None, caminho: str, padrao: str = "") -> str:
    e = _find(raiz, caminho)
    return (e.text or "").strip() if e is not None and e.text else padrao


def _num(valor: str, casas: int = 2) -> str:
    try:
        d = Decimal(valor or "0")
    except InvalidOperation:
        return valor
    texto = f"{d:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def _doc(valor: str) -> str:
    if len(valor) == 14:
        return f"{valor[:2]}.{valor[2:5]}.{valor[5:8]}/{valor[8:12]}-{valor[12:]}"
    if len(valor) == 11:
        return f"{valor[:3]}.{valor[3:6]}.{valor[6:9]}-{valor[9:]}"
    return valor


def _cep(valor: str) -> str:
    return f"{valor[:5]}-{valor[5:]}" if len(valor) == 8 else valor


def _data(valor: str) -> tuple[str, str]:
    try:
        d = datetime.fromisoformat(valor)
    except ValueError:
        return valor, ""
    return d.strftime("%d/%m/%Y"), d.strftime("%H:%M:%S")


@dataclass
class _Item:
    codigo: str
    descricao: str
    ncm: str
    csosn: str
    cfop: str
    unidade: str
    quantidade: str
    unitario: str
    total: str


@dataclass
class _Dados:
    chave: str = ""
    numero: str = ""
    serie: str = ""
    tp_nf: str = "1"
    ambiente: str = "1"
    natureza: str = ""
    emissao: str = ""
    saida: str = ""
    protocolo: str = ""
    emit: dict[str, str] = field(default_factory=dict)
    dest: dict[str, str] = field(default_factory=dict)
    tot: dict[str, str] = field(default_factory=dict)
    mod_frete: str = "9"
    itens: list[_Item] = field(default_factory=list)
    info: str = ""


def _ler(proc_xml: str) -> _Dados:
    texto = proc_xml.split("?>", 1)[1] if proc_xml.startswith("<?xml") else proc_xml
    raiz = ET.fromstring(texto)  # noqa: S314 — XML que nós mesmos geramos e a SEFAZ autorizou
    inf = next((e for e in raiz.iter() if _local(e.tag) == "infNFe"), None)
    if inf is None:
        raise ValueError("XML sem infNFe")
    prot = next((e for e in raiz.iter() if _local(e.tag) == "infProt"), None)
    d = _Dados()
    d.chave = inf.get("Id", "")[3:]
    d.numero, d.serie = _t(inf, "ide/nNF"), _t(inf, "ide/serie")
    d.tp_nf, d.ambiente = _t(inf, "ide/tpNF", "1"), _t(inf, "ide/tpAmb", "1")
    d.natureza = _t(inf, "ide/natOp")
    d.emissao = _t(inf, "ide/dhEmi")
    d.saida = _t(inf, "ide/dhSaiEnt")
    if prot is not None:
        quando = " ".join(_data(_t(prot, "dhRecbto")))
        d.protocolo = f"{_t(prot, 'nProt')} - {quando}".strip(" -")
    for chave, base in (("emit", "emit"), ("dest", "dest")):
        end = "enderEmit" if chave == "emit" else "enderDest"
        alvo = d.emit if chave == "emit" else d.dest
        alvo.update(
            nome=_t(inf, f"{base}/xNome"),
            fantasia=_t(inf, f"{base}/xFant"),
            doc=_t(inf, f"{base}/CNPJ") or _t(inf, f"{base}/CPF"),
            ie=_t(inf, f"{base}/IE"),
            lgr=_t(inf, f"{base}/{end}/xLgr"),
            nro=_t(inf, f"{base}/{end}/nro"),
            cpl=_t(inf, f"{base}/{end}/xCpl"),
            bairro=_t(inf, f"{base}/{end}/xBairro"),
            mun=_t(inf, f"{base}/{end}/xMun"),
            uf=_t(inf, f"{base}/{end}/UF"),
            cep=_t(inf, f"{base}/{end}/CEP"),
            fone=_t(inf, f"{base}/{end}/fone"),
        )
    tot = _find(inf, "total/ICMSTot")
    for campo in (
        "vBC",
        "vICMS",
        "vBCST",
        "vST",
        "vProd",
        "vFrete",
        "vSeg",
        "vDesc",
        "vOutro",
        "vIPI",
        "vNF",
        "vICMSUFDest",
        "vFCPUFDest",
    ):
        d.tot[campo] = _t(tot, campo, "0.00")
    d.mod_frete = _t(inf, "transp/modFrete", "9")
    for det in (e for e in inf if _local(e.tag) == "det"):
        icms = _find(det, "imposto/ICMS")
        grupo = next(iter(icms), None) if icms is not None else None
        csosn = _t(grupo, "CSOSN") or _t(grupo, "CST")
        d.itens.append(
            _Item(
                codigo=_t(det, "prod/cProd"),
                descricao=_t(det, "prod/xProd"),
                ncm=_t(det, "prod/NCM"),
                csosn=f"{_t(grupo, 'orig')}{csosn}",
                cfop=_t(det, "prod/CFOP"),
                unidade=_t(det, "prod/uCom"),
                quantidade=_num(_t(det, "prod/qCom"), 4),
                unitario=_num(_t(det, "prod/vUnCom")),
                total=_num(_t(det, "prod/vProd")),
            )
        )
    d.info = _t(inf, "infAdic/infCpl")
    return d


class _Pagina:
    def __init__(self, c: Canvas) -> None:
        self.c = c

    def y(self, topo_mm: float) -> float:
        return float(H - M - topo_mm * mm)

    def caixa(
        self,
        x: float,
        topo: float,
        w: float,
        h: float,
        rotulo: str,
        valor: str = "",
        *,
        alinhar: str = "l",
        tam: float = 8,
    ) -> None:
        """x/w em pontos; topo/h em mm a partir do topo da área útil."""
        c = self.c
        base = self.y(topo + h)
        c.rect(x, base, w, h * mm)
        c.setFont("Helvetica", 5.5)
        c.drawString(x + 1.2, self.y(topo) - 6, rotulo.upper())
        if valor:
            c.setFont("Helvetica-Bold" if tam >= 8 else "Helvetica", tam)
            texto = _cabe(valor, w - 3, "Helvetica-Bold", tam)
            yv = base + 2.2
            if alinhar == "r":
                c.drawRightString(x + w - 1.5, yv, texto)
            elif alinhar == "c":
                c.drawCentredString(x + w / 2, yv, texto)
            else:
                c.drawString(x + 1.5, yv, texto)

    def titulo(self, topo: float, texto: str) -> None:
        self.c.setFont("Helvetica-Bold", 6.5)
        self.c.drawString(M, self.y(topo) - 6, texto)


def _cabe(texto: str, largura: float, fonte: str, tam: float) -> str:
    if stringWidth(texto, fonte, tam) <= largura:
        return texto
    while texto and stringWidth(texto + "…", fonte, tam) > largura:
        texto = texto[:-1]
    return texto + "…"


def _quebrar(texto: str, largura: float, fonte: str, tam: float) -> list[str]:
    linhas: list[str] = []
    for paragrafo in texto.split("\n"):
        atual = ""
        for palavra in paragrafo.split():
            teste = f"{atual} {palavra}".strip()
            if stringWidth(teste, fonte, tam) <= largura:
                atual = teste
            else:
                if atual:
                    linhas.append(atual)
                atual = palavra
        linhas.append(atual)
    return linhas


COLUNAS = (  # rótulo, largura relativa, alinhamento
    ("Código", 14, "l"),
    ("Descrição do produto/serviço", 56, "l"),
    ("NCM/SH", 13, "c"),
    ("CSOSN", 9, "c"),
    ("CFOP", 8, "c"),
    ("Un", 6, "c"),
    ("Quant.", 13, "r"),
    ("Valor unit.", 14, "r"),
    ("Valor total", 15, "r"),
    ("BC ICMS", 11, "r"),
    ("V. ICMS", 10, "r"),
    ("Alíq. ICMS", 11, "r"),
)


def _cabecalho(p: _Pagina, d: _Dados, folha: int, folhas: int) -> float:
    """Desenha canhoto + identificação; devolve o topo (mm) livre abaixo."""
    c, e = p.c, d.emit
    # Canhoto
    larg_nf = 38 * mm
    p.caixa(
        M,
        0,
        LARGURA - larg_nf,
        8,
        f"Recebemos de {e['nome']} os produtos constantes da nota fiscal indicada ao lado",
    )
    p.caixa(M, 8, 40 * mm, 8, "Data de recebimento")
    p.caixa(
        M + 40 * mm, 8, LARGURA - larg_nf - 40 * mm, 8, "Identificação e assinatura do recebedor"
    )
    c.rect(M + LARGURA - larg_nf, p.y(16), larg_nf, 16 * mm)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(M + LARGURA - larg_nf / 2, p.y(6), "NF-e")
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(
        M + LARGURA - larg_nf / 2, p.y(11), f"Nº {int(d.numero or 0):09,d}".replace(",", ".")
    )
    c.drawCentredString(M + LARGURA - larg_nf / 2, p.y(14.5), f"SÉRIE {d.serie}")
    c.setDash(2, 2)
    c.line(M, p.y(18), M + LARGURA, p.y(18))
    c.setDash()

    # Emitente | DANFE | chave
    topo, alt = 20.0, 32.0
    w1, w2 = 78 * mm, 34 * mm
    w3 = LARGURA - w1 - w2
    c.rect(M, p.y(topo + alt), w1, alt * mm)
    c.setFont("Helvetica", 5.5)
    c.drawString(M + 1.2, p.y(topo) - 6, "IDENTIFICAÇÃO DO EMITENTE")
    c.setFont("Helvetica-Bold", 9)
    linhas = _quebrar(e["nome"], w1 - 4, "Helvetica-Bold", 9)[:2]
    for n, linha in enumerate(linhas):
        c.drawCentredString(M + w1 / 2, p.y(topo + 7 + n * 4), linha)
    c.setFont("Helvetica", 7)
    end = f"{e['lgr']}, {e['nro']}" + (f" - {e['cpl']}" if e["cpl"] else "")
    detalhes = [
        end,
        f"{e['bairro']} - CEP {_cep(e['cep'])}",
        f"{e['mun']} - {e['uf']}" + (f"  Fone: {e['fone']}" if e["fone"] else ""),
    ]
    for n, linha in enumerate(detalhes):
        c.drawCentredString(
            M + w1 / 2, p.y(topo + 17 + n * 3.6), _cabe(linha, w1 - 4, "Helvetica", 7)
        )

    x2 = M + w1
    c.rect(x2, p.y(topo + alt), w2, alt * mm)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(x2 + w2 / 2, p.y(topo + 6), "DANFE")
    c.setFont("Helvetica", 6)
    c.drawCentredString(x2 + w2 / 2, p.y(topo + 9.5), "Documento Auxiliar da")
    c.drawCentredString(x2 + w2 / 2, p.y(topo + 12), "Nota Fiscal Eletrônica")
    c.drawString(x2 + 3 * mm, p.y(topo + 16.5), "0 - ENTRADA")
    c.drawString(x2 + 3 * mm, p.y(topo + 19.5), "1 - SAÍDA")
    c.rect(x2 + w2 - 9 * mm, p.y(topo + 20.5), 5 * mm, 5 * mm)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(x2 + w2 - 6.5 * mm, p.y(topo + 19.3), d.tp_nf)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(
        x2 + w2 / 2, p.y(topo + 24.5), f"Nº {int(d.numero or 0):09,d}".replace(",", ".")
    )
    c.drawCentredString(x2 + w2 / 2, p.y(topo + 28), f"SÉRIE {d.serie}  FOLHA {folha}/{folhas}")

    x3 = x2 + w2
    c.rect(x3, p.y(topo + alt), w3, alt * mm)
    barras = Code128(d.chave, barHeight=11 * mm, barWidth=0.24 * mm, quiet=False)
    barras.drawOn(c, x3 + (w3 - barras.width) / 2, p.y(topo + 13))
    c.setFont("Helvetica", 5.5)
    c.drawString(x3 + 1.2, p.y(topo + 15) - 4, "CHAVE DE ACESSO")
    c.setFont("Helvetica-Bold", 7.5)
    grupos = " ".join(d.chave[i : i + 4] for i in range(0, len(d.chave), 4))
    c.drawCentredString(x3 + w3 / 2, p.y(topo + 20.5), grupos)
    c.setFont("Helvetica", 6)
    c.drawCentredString(
        x3 + w3 / 2, p.y(topo + 25), "Consulta de autenticidade no portal nacional da NF-e"
    )
    c.drawCentredString(
        x3 + w3 / 2,
        p.y(topo + 28),
        "www.nfe.fazenda.gov.br/portal ou no site da Sefaz Autorizadora",
    )

    topo += alt
    p.caixa(M, topo, w1 + w2, 7, "Natureza da operação", d.natureza)
    p.caixa(M + w1 + w2, topo, w3, 7, "Protocolo de autorização de uso", d.protocolo, alinhar="c")
    topo += 7
    terco = LARGURA / 3
    p.caixa(M, topo, terco, 7, "Inscrição estadual", e["ie"])
    p.caixa(M + terco, topo, terco, 7, "Insc. estadual do subst. trib.")
    p.caixa(M + 2 * terco, topo, terco, 7, "CNPJ", _doc(e["doc"]))
    return topo + 9


def _corpo(p: _Pagina, d: _Dados, topo: float) -> float:
    ds = d.dest
    p.titulo(topo, "DESTINATÁRIO / REMETENTE")
    topo += 3.5
    emissao_data, _ = _data(d.emissao)
    saida_data, saida_hora = _data(d.saida) if d.saida else ("", "")
    wd = 30 * mm
    p.caixa(M, topo, LARGURA - 2 * wd - 15 * mm, 7, "Nome / razão social", ds["nome"])
    p.caixa(M + LARGURA - 2 * wd - 15 * mm, topo, wd + 15 * mm, 7, "CNPJ / CPF", _doc(ds["doc"]))
    p.caixa(M + LARGURA - wd, topo, wd, 7, "Data da emissão", emissao_data, alinhar="c")
    topo += 7
    end = f"{ds['lgr']}, {ds['nro']}" + (f" - {ds['cpl']}" if ds["cpl"] else "")
    p.caixa(M, topo, LARGURA - 2 * wd - 45 * mm, 7, "Endereço", end)
    p.caixa(M + LARGURA - 2 * wd - 45 * mm, topo, 45 * mm, 7, "Bairro / distrito", ds["bairro"])
    p.caixa(M + LARGURA - 2 * wd, topo, wd, 7, "CEP", _cep(ds["cep"]), alinhar="c")
    p.caixa(M + LARGURA - wd, topo, wd, 7, "Data da saída", saida_data, alinhar="c")
    topo += 7
    p.caixa(M, topo, LARGURA - 2 * wd - 60 * mm, 7, "Município", ds["mun"])
    p.caixa(M + LARGURA - 2 * wd - 60 * mm, topo, 30 * mm, 7, "Fone / fax", ds["fone"])
    p.caixa(M + LARGURA - 2 * wd - 30 * mm, topo, 10 * mm, 7, "UF", ds["uf"], alinhar="c")
    p.caixa(M + LARGURA - 2 * wd - 20 * mm, topo, wd + 20 * mm, 7, "Inscrição estadual", ds["ie"])
    p.caixa(M + LARGURA - wd, topo, wd, 7, "Hora da saída", saida_hora, alinhar="c")
    topo += 9

    t = d.tot
    p.titulo(topo, "CÁLCULO DO IMPOSTO")
    topo += 3.5
    linha1 = [
        ("Base de cálc. do ICMS", t["vBC"]),
        ("Valor do ICMS", t["vICMS"]),
        ("Base cálc. ICMS ST", t["vBCST"]),
        ("Valor do ICMS ST", t["vST"]),
        ("V. ICMS UF destino", t["vICMSUFDest"]),
        ("Valor total dos produtos", t["vProd"]),
    ]
    linha2 = [
        ("Valor do frete", t["vFrete"]),
        ("Valor do seguro", t["vSeg"]),
        ("Desconto", t["vDesc"]),
        ("Outras despesas", t["vOutro"]),
        ("Valor total do IPI", t["vIPI"]),
        ("Valor total da nota", t["vNF"]),
    ]
    for linha in (linha1, linha2):
        w = LARGURA / len(linha)
        for n, (rotulo, valor) in enumerate(linha):
            p.caixa(M + n * w, topo, w, 7, rotulo, _num(valor), alinhar="r")
        topo += 7
    topo += 2

    p.titulo(topo, "TRANSPORTADOR / VOLUMES TRANSPORTADOS")
    topo += 3.5
    p.caixa(M, topo, 70 * mm, 7, "Razão social")
    p.caixa(
        M + 70 * mm, topo, 45 * mm, 7, "Frete por conta", MOD_FRETE.get(d.mod_frete, d.mod_frete)
    )
    p.caixa(M + 115 * mm, topo, LARGURA - 115 * mm, 7, "CNPJ / CPF")
    return topo + 9


def _tabela_topo(p: _Pagina, topo: float) -> tuple[float, list[float]]:
    p.titulo(topo, "DADOS DOS PRODUTOS / SERVIÇOS")
    topo += 3.5
    soma = sum(c[1] for c in COLUNAS)
    larguras = [LARGURA * c[1] / soma for c in COLUNAS]
    x = M
    p.c.setFont("Helvetica", 5.5)
    for (rotulo, _, _), w in zip(COLUNAS, larguras, strict=True):
        p.c.rect(x, p.y(topo + 5), w, 5 * mm)
        p.c.drawCentredString(x + w / 2, p.y(topo + 3.3), rotulo.upper())
        x += w
    return topo + 5, larguras


def _linhas_item(item: _Item, larguras: list[float]) -> list[list[str]]:
    desc = _quebrar(item.descricao, larguras[1] - 3, "Helvetica", 6.5) or [""]
    valores = [
        item.codigo,
        "",
        item.ncm,
        item.csosn,
        item.cfop,
        item.unidade,
        item.quantidade,
        item.unitario,
        item.total,
        "0,00",
        "0,00",
        "0,00",
    ]
    linhas = []
    for n, d in enumerate(desc):
        linha = valores[:] if n == 0 else [""] * len(valores)
        linha[1] = d
        linhas.append(linha)
    return linhas


def _rodape(p: _Pagina, d: _Dados) -> None:
    altura = 30.0
    topo = (H - 2 * M) / mm - altura
    p.titulo(topo - 3.5, "DADOS ADICIONAIS")
    w1 = LARGURA * 0.65
    c = p.c
    c.rect(M, p.y(topo + altura), w1, altura * mm)
    c.rect(M + w1, p.y(topo + altura), LARGURA - w1, altura * mm)
    c.setFont("Helvetica", 5.5)
    c.drawString(M + 1.2, p.y(topo) - 6, "INFORMAÇÕES COMPLEMENTARES")
    c.drawString(M + w1 + 1.2, p.y(topo) - 6, "RESERVADO AO FISCO")
    c.setFont("Helvetica", 6.5)
    for n, linha in enumerate(_quebrar(d.info, w1 - 4, "Helvetica", 6.5)[:11]):
        c.drawString(M + 1.5, p.y(topo + 5 + n * 2.6), linha)


def _marca(c: Canvas, texto: str) -> None:
    c.saveState()
    c.setFillColorRGB(0.85, 0.15, 0.15, alpha=0.18)
    c.setFont("Helvetica-Bold", 46)
    c.translate(W / 2, H / 2)
    c.rotate(35)
    c.drawCentredString(0, 0, texto)
    c.restoreState()


def gerar_danfe(proc_xml: str, *, cancelada: bool = False) -> bytes:
    """PDF da DANFE a partir do nfeProc (ou da NFe assinada, sem protocolo)."""
    d = _ler(proc_xml)
    buf = io.BytesIO()
    c = Canvas(buf, pagesize=A4)
    c.setTitle(f"DANFE {d.numero} - {d.chave}")
    p = _Pagina(c)
    rodape_topo = (H - 2 * M) / mm - 34.0

    # pré-calcula as linhas para saber quantas folhas
    soma = sum(col[1] for col in COLUNAS)
    larguras = [LARGURA * col[1] / soma for col in COLUNAS]
    linhas = [ln for item in d.itens for ln in _linhas_item(item, larguras)]
    passo = 3.4
    cab = 80.0  # canhoto + identificação + tabela (folhas seguintes)
    primeira = int((rodape_topo - (cab + 62)) / passo) - 1
    seguintes = int((rodape_topo - cab) / passo) - 1
    folhas = 1 + max(0, -(-(len(linhas) - primeira) // seguintes))

    restante = linhas
    for folha in range(1, folhas + 1):
        topo = _cabecalho(p, d, folha, folhas)
        if folha == 1:
            topo = _corpo(p, d, topo)
        topo, _ = _tabela_topo(p, topo)
        cabem = int((rodape_topo - topo) / passo) - 1
        agora, restante = restante[:cabem], restante[cabem:]
        c.setFont("Helvetica", 6.5)
        for linha in agora:
            x = M
            for (_, _, alinhar), w, valor in zip(COLUNAS, larguras, linha, strict=True):
                yv = p.y(topo + passo - 0.9)
                texto = _cabe(valor, w - 2, "Helvetica", 6.5)
                if alinhar == "r":
                    c.drawRightString(x + w - 1, yv, texto)
                elif alinhar == "c":
                    c.drawCentredString(x + w / 2, yv, texto)
                else:
                    c.drawString(x + 1, yv, texto)
                x += w
            topo += passo
        c.rect(M, p.y(rodape_topo - 1), LARGURA, (rodape_topo - 1 - topo + len(agora) * passo) * mm)
        _rodape(p, d)
        if d.ambiente == "2":
            _marca(c, "SEM VALOR FISCAL")
        if cancelada:
            _marca(c, "NF-e CANCELADA")
        c.showPage()
    c.save()
    return buf.getvalue()
