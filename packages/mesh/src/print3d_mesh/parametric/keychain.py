"""Chaveiro "Letra + Nome" (spec 2.5): letra grande (cor 1) com o nome em relevo (cor 2).

Construção: o nome fica sobre uma faixa sólida (contorno do nome) que atravessa a letra, e a
argola sai da ponta da faixa. Assim a peça é um corpo só em qualquer letra (L, O, J...) e o
nome nunca fica "no ar". Imprime com AMS (troca automática) ou com pausa na altura do nome.
"""

from typing import Annotated, Literal, Self

import trimesh
from pydantic import BaseModel, Field, StringConstraints, model_validator

from print3d_mesh.parametric.base import ParametricModel
from print3d_mesh.parametric.fonts import FONTS, scad_font_uses
from print3d_mesh.parametric.openscad import scad_string

Style = Literal["letra_nome", "letra_cursiva_nome", "so_nome", "inicial_data"]
FontKey = Literal["bold", "semibold", "condensada", "cursiva", "retro", "manuscrita"]

LETTER_PATTERN = r"^[A-ZÁÉÍÓÚÂÊÔÃÕÀÇ0-9]$"
NAME_PATTERN = r"^[A-Za-zÁÉÍÓÚÂÊÔÃÕÀÇáéíóúâêôãõàçüÜ0-9 '.\-/&]+$"


class KeychainParams(BaseModel):
    style: Style = Field(default="letra_nome", title="Estilo")
    letter: Annotated[str, StringConstraints(pattern=LETTER_PATTERN)] | None = Field(
        default="J", title="Letra", description="A-Z, acentuadas, Ç ou número"
    )
    name: Annotated[str, StringConstraints(min_length=1, max_length=14, pattern=NAME_PATTERN)] = (
        Field(default="Jefferson", title="Nome ou data", description="até 14 caracteres")
    )
    letter_font: FontKey | None = Field(default=None, title="Fonte da letra")
    name_font: FontKey | None = Field(default=None, title="Fonte do nome")
    letter_size_mm: float = Field(default=40, ge=25, le=60, title="Tamanho da letra (mm)")
    base_mm: float = Field(default=4, ge=3, le=6, title="Espessura (mm)")
    relief_mm: float = Field(default=1.0, ge=0.6, le=2.0, title="Relevo do nome (mm)")
    ring_hole: bool = Field(default=True, title="Furo para argola")
    min_text_mm: float = Field(
        default=3.5,
        ge=2.0,
        le=8.0,
        title="Altura mínima legível (mm)",
        description="depende do bico; 3,5 mm para bico 0,4",
    )

    @model_validator(mode="after")
    def _consistente(self) -> Self:
        if self.style != "so_nome" and not self.letter:
            raise ValueError("este estilo precisa de uma letra")
        if self.style == "inicial_data" and not any(c.isdigit() for c in self.name):
            raise ValueError(
                "no estilo inicial + data, o texto deve ser uma data (ex.: 12/10/2026)"
            )
        return self

    def fonts(self) -> tuple[str, str]:
        defaults: dict[Style, tuple[str, str]] = {
            "letra_nome": ("bold", "cursiva"),
            "letra_cursiva_nome": ("manuscrita", "semibold"),
            "so_nome": ("bold", "cursiva"),
            "inicial_data": ("bold", "semibold"),
        }
        letter_default, name_default = defaults[self.style]
        return (self.letter_font or letter_default, self.name_font or name_default)


class KeychainLetterName(ParametricModel[KeychainParams]):
    slug = "chaveiro-letra-nome"
    title = "Chaveiro letra + nome"
    niche = "chaveiros"
    description = "Letra grande com o nome em relevo por cima, em duas cores."
    params_model = KeychainParams

    def parts(self, params: KeychainParams) -> list[str]:
        return ["base", "nome"]

    def scad(self, params: KeychainParams, part: str) -> str:
        letter_font, name_font = params.fonts()
        only_name = params.style == "so_nome"
        size = params.letter_size_mm
        # Largura do nome: atravessa a letra; sem letra, o nome é a peça inteira.
        name_width = size * (1.5 if only_name else 1.05)
        lines = [
            scad_font_uses(),
            "$fn = 64;",
            f"PART = {scad_string(part)};",
            f"L = {scad_string(params.letter or '')};",
            f"N = {scad_string(params.name)};",
            f"S = {size};",
            f"BASE = {params.base_mm};",
            f"REL = {params.relief_mm};",
            f"NAME_W = {name_width:.2f};",
            f"LF = {scad_string(FONTS[letter_font].scad_name)};",
            f"NF = {scad_string(FONTS[name_font].scad_name)};",
            f"ONLY_NAME = {'true' if only_name else 'false'};",
            f"HOLE = {'true' if params.ring_hole else 'false'};",
            _KEYCHAIN_SCAD,
        ]
        return "\n".join(lines)

    def check(self, params: KeychainParams, meshes: dict[str, trimesh.Trimesh]) -> list[str]:
        issues: list[str] = []
        base, name = meshes.get("base"), meshes.get("nome")
        if base is not None and len(base.split(only_watertight=False)) > 1:
            issues.append("a base ficou em mais de um pedaço (letra solta da faixa do nome)")
        if name is not None:
            text_height = float(name.extents[1])
            if text_height < params.min_text_mm:
                issues.append(
                    f"nome ficou com {text_height:.1f} mm de altura (mínimo legível "
                    f"{params.min_text_mm} mm): aumente a letra, abrevie o nome ou troque a fonte"
                )
        return issues


_KEYCHAIN_SCAD = """
RING_R = 4.5;
HOLE_R = 2.2;

module letter2d() text(L, size = S, font = LF, halign = "center", valign = "center");
module name2d() resize([NAME_W, 0], auto = true)
    text(N, size = S * 0.3, font = NF, halign = "center", valign = "center");
module band2d() hull() offset(r = 1.6) name2d();
module ring2d() translate([-NAME_W / 2 - 2.5, 0]) circle(r = RING_R);

module base2d() difference() {
    union() {
        if (!ONLY_NAME) letter2d();
        band2d();
        if (HOLE) ring2d();
    }
    if (HOLE) translate([-NAME_W / 2 - 2.5, 0]) circle(r = HOLE_R);
}

if (PART == "base") linear_extrude(BASE) base2d();
if (PART == "nome") translate([0, 0, BASE]) linear_extrude(REL) name2d();
"""
