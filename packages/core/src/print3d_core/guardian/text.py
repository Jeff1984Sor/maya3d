"""Normalização de texto para o Guardião: acentos, caixa, separadores, leetspeak e soletração.

Pega "CrossFit", "cross-fit", "C R O S S F I T", "cr0ssf1t" e "Crossfits" com o mesmo termo,
sem casar pedaços de palavras ("lego" não casa em "colégio").
"""

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

_LEET = str.maketrans(
    {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"}
)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_SPELLED = re.compile(r"\b(?:[a-z0-9] ){2,}[a-z0-9]\b")  # "c r o s s" → "cross"


def fold(text: str) -> str:
    """Minúsculas e sem acento."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def _spaced(text: str) -> str:
    return " ".join(_NON_ALNUM.sub(" ", text).split())


@dataclass(frozen=True)
class Searchable:
    """Variantes do mesmo texto; um termo casa se aparecer em qualquer uma delas."""

    variants: tuple[str, ...]

    @classmethod
    def of(cls, *parts: str | None) -> "Searchable":
        raw = fold(" \n ".join(p for p in parts if p))
        spaced = _spaced(raw)
        joined = _spaced(re.sub(r"(?<=[a-z0-9])[-_.'](?=[a-z0-9])", "", raw))  # cross-fit
        spelled = _SPELLED.sub(lambda m: m.group(0).replace(" ", ""), spaced)
        leet = _spaced(raw.translate(_LEET))
        return cls(tuple(dict.fromkeys((spaced, joined, spelled, leet))))

    def has(self, term: str) -> bool:
        pattern = _term_pattern(term)
        return any(pattern.search(v) for v in self.variants)

    def first(self, terms: tuple[str, ...] | frozenset[str]) -> str | None:
        return next((t for t in terms if self.has(t)), None)


@lru_cache(maxsize=4096)
def _term_pattern(term: str) -> re.Pattern[str]:
    words = _spaced(fold(term))
    # palavra inteira, aceitando plural simples (freio/freios, anilha/anilhas)
    return re.compile(rf"(?<![a-z0-9]){re.escape(words)}(?:s|es)?(?![a-z0-9])")
