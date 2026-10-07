"""Texto nos modelos: caracteres aceitos e tamanho que cabe num espaço.

O OpenSCAD não mede texto antes de gerar; estimamos pela largura média dos caracteres da
fonte (conservador) e conferimos depois na malha (`check` de cada modelo).
"""

import math
from typing import Literal

FontKey = Literal["bold", "semibold", "condensada", "cursiva", "retro", "manuscrita"]

TEXT_PATTERN = r"^[A-Za-zÁÉÍÓÚÂÊÔÃÕÀÇáéíóúâêôãõàçüÜ0-9 '.,!?:\-/&+♥]+$"
DATE_PATTERN = r"^[0-9]{1,2}[/.\-][0-9]{1,2}([/.\-][0-9]{2,4})?$"

# largura média de um caractere / tamanho da fonte: estimativa conservadora (o `check` mede depois)
WIDTH_FACTOR: dict[str, float] = {
    "bold": 0.74,
    "semibold": 0.7,
    "condensada": 0.5,
    "cursiva": 0.72,
    "retro": 0.62,
    "manuscrita": 0.58,
}
CAP_HEIGHT = 0.72  # altura de maiúscula ≈ 72% do tamanho da fonte


def fit_size(text: str, max_width: float, max_size: float, font: str) -> float:
    """Maior tamanho de fonte que deixa o texto dentro da largura (e até max_size)."""
    chars = max(len(text.strip()), 1)
    size = min(max_size, max_width / (chars * WIDTH_FACTOR.get(font, 0.74)))
    return math.floor(size * 100) / 100  # arredonda para baixo: nunca passa da largura


def legibility_issue(label: str, size: float, min_text_mm: float) -> str | None:
    height = size * CAP_HEIGHT
    if height >= min_text_mm:
        return None
    return (
        f"{label} ficou com {height:.1f} mm de altura (mínimo legível {min_text_mm} mm): "
        "aumente a peça ou encurte o texto"
    )


def overflow_issue(label: str, extent: float, room: float) -> str | None:
    if extent <= room + 0.5:
        return None
    return f"{label} passou da área ({extent:.1f} mm em {room:.1f} mm): encurte o texto"
