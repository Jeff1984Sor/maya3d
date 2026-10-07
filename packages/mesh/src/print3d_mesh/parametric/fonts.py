"""Fontes permitidas nos produtos. Só licença de uso comercial (spec 2.5: Google Fonts / OFL),
versionadas junto do código com o arquivo de licença ao lado (fonts/OFL-*.txt)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Final

FONTS_DIR: Final = Path(__file__).parent / "fonts"


@dataclass(frozen=True)
class FontSpec:
    key: str
    label: str
    file: str
    scad_name: str  # nome que o OpenSCAD usa em text(font=...)
    license: str = "OFL-1.1"


FONTS: Final[dict[str, FontSpec]] = {
    f.key: f
    for f in (
        FontSpec("bold", "Bold (Poppins)", "Poppins-Bold.ttf", "Poppins:style=Bold"),
        FontSpec(
            "semibold", "Semibold (Poppins)", "Poppins-SemiBold.ttf", "Poppins:style=SemiBold"
        ),
        FontSpec("condensada", "Condensada (Anton)", "Anton-Regular.ttf", "Anton"),
        FontSpec("cursiva", "Cursiva (Pacifico)", "Pacifico-Regular.ttf", "Pacifico"),
        FontSpec("retro", "Retrô (Lobster)", "Lobster-Regular.ttf", "Lobster"),
        FontSpec("manuscrita", "Manuscrita (Great Vibes)", "GreatVibes-Regular.ttf", "Great Vibes"),
    )
}


def scad_font_uses() -> str:
    """Linhas `use <...>` que registram as fontes no OpenSCAD (sem instalar no sistema)."""
    return "\n".join(f"use <{(FONTS_DIR / f.file).as_posix()}>" for f in FONTS.values())
