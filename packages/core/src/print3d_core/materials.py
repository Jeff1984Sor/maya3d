"""Propriedades físicas de materiais para comparar a MESMA peça em materiais diferentes.

Gramas vêm do fatiador para um material de referência; em outro material, o volume é o
mesmo e a massa muda com a densidade. Densidades típicas de filamento (g/cm³) — podem ser
sobrescritas por material no cadastro (marcas variam um pouco).
"""

from decimal import Decimal
from typing import Final

DEFAULT_DENSITY_G_CM3: Final[dict[str, Decimal]] = {
    "PLA": Decimal("1.24"),
    "PETG": Decimal("1.27"),
    "ASA": Decimal("1.07"),
    "ABS": Decimal("1.04"),
    "TPU": Decimal("1.21"),
    "PA": Decimal("1.14"),
    "PC": Decimal("1.20"),
    "RESINA": Decimal("1.15"),
}


def density_for(kind: str, override: Decimal | None = None) -> Decimal:
    """Densidade do material: a do cadastro, senão a típica do tipo, senão a do PLA."""
    if override is not None and override > 0:
        return override
    return DEFAULT_DENSITY_G_CM3.get(kind.upper(), DEFAULT_DENSITY_G_CM3["PLA"])


def convert_grams(grams: Decimal, from_density: Decimal, to_density: Decimal) -> Decimal:
    """Mesma peça (mesmo volume) em outro material: massa proporcional à densidade."""
    if from_density <= 0 or to_density <= 0:
        raise ValueError("densidade deve ser positiva")
    return (grams * to_density / from_density).quantize(Decimal("0.1"))
