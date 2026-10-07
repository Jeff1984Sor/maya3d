"""Conferências determinísticas sobre o texto da IA (independem do modelo)."""

import re

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
_CONTACT = re.compile(
    r"(https?://|www\.|\.com\b|\.br\b|@\w|whats\s?app|wpp|zap\b|instagram|telefone|"
    r"\(\d{2}\)\s?\d|\b\d{4,5}-\d{4}\b|e-?mail)",
    re.IGNORECASE,
)


def _norm(n: str) -> str:
    return n.replace(",", ".").rstrip("0").rstrip(".") if "." in n or "," in n else n


def unknown_numbers(text: str, facts: str) -> list[str]:
    """Números do texto que não aparecem nos fatos (a IA não pode criar números)."""
    known = {_norm(n) for n in _NUMBER.findall(facts)}
    found = [_norm(n) for n in _NUMBER.findall(text)]
    return sorted({n for n in found if n not in known and n != "3"})  # "3" de "impressão 3D"


def contact_info(text: str) -> list[str]:
    """Links/contatos externos — proibidos em anúncios de marketplace."""
    return sorted({m.group(0).lower() for m in _CONTACT.finditer(text)})
