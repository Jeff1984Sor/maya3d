"""Montagem de XML já na forma canônica (C14N 1.0) — sem depender de lxml.

A NF-e assina o elemento `infNFe` canonicalizado. Como nós mesmos geramos o XML, escrevemos
direto na forma canônica: sem declaração, sem tag vazia abreviada (`<a></a>`), atributos em
ordem, escapes da C14N e nenhum espaço entre elementos. Assim o texto enviado é exatamente o
texto assinado (os testes conferem contra o `xml.etree.ElementTree.canonicalize`).
"""

import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal

# O schema da NF-e (TString) aceita só caracteres de 0x20 a 0xFF, sem espaço nas pontas.
_TROCAS = {
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
    "\u201c": '"',
    "\u201d": '"',
    "\u2018": "'",
    "\u2019": "'",
    "\u2026": "...",
    "\u00a0": " ",
    "\u2022": "-",
}


def limpar(texto: str, limite: int | None = None) -> str:
    """Texto aceito pelo schema: só Latin-1 visível, espaços simples, sem pontas."""
    out = []
    for ch in unicodedata.normalize("NFC", texto):
        ch = _TROCAS.get(ch, ch)
        for c in ch:
            if c in "\t\r\n":
                out.append(" ")
            elif 0x20 <= ord(c) <= 0xFF and c != "\x7f":
                out.append(c)
            elif ord(c) > 0xFF:  # tenta tirar o acento de letras fora do Latin-1
                base = unicodedata.normalize("NFKD", c).encode("latin-1", "ignore").decode()
                out.append(base)
    limpo = re.sub(r" {2,}", " ", "".join(out)).strip()
    return limpo[:limite].strip() if limite else limpo


def esc_texto(valor: str) -> str:
    return valor.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def esc_attr(valor: str) -> str:
    return (
        valor.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace('"', "&quot;")
        .replace("\t", "&#x9;")
        .replace("\n", "&#xA;")
        .replace("\r", "&#xD;")
    )


def _abre(tag: str, attrs: dict[str, str] | None, ns: str | None) -> str:
    partes = [tag]
    if ns:
        partes.append(f'xmlns="{esc_attr(ns)}"')
    for nome in sorted(attrs or {}):  # C14N: atributos sem prefixo em ordem de código
        partes.append(f'{nome}="{esc_attr((attrs or {})[nome])}"')
    return "<" + " ".join(partes) + ">"


def el(
    tag: str, *filhos: str | None, attrs: dict[str, str] | None = None, ns: str | None = None
) -> str:
    """Elemento com filhos já montados (filho None é omitido)."""
    return _abre(tag, attrs, ns) + "".join(f for f in filhos if f) + f"</{tag}>"


def t(tag: str, valor: str | int | Decimal | None, *, limite: int | None = None) -> str | None:
    """Elemento folha com texto. Vazio/None → omitido (campo opcional)."""
    if valor is None:
        return None
    texto = valor if isinstance(valor, str) else str(valor)
    if isinstance(valor, str):
        texto = limpar(texto, limite)
    if texto == "":
        return None
    return f"<{tag}>{esc_texto(texto)}</{tag}>"


def dec(valor: Decimal | int | str, casas: int = 2) -> str:
    q = Decimal(1).scaleb(-casas)
    return str(Decimal(valor).quantize(q, rounding=ROUND_HALF_UP))


def so_digitos(valor: str | None) -> str:
    return re.sub(r"\D", "", valor or "")
