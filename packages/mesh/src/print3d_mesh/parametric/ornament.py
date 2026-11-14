"""Enfeites de Natal personalizados (desenhos próprios), em duas cores e com argola para fita.

- Floco com nome: aro com borda de floco de neve e o nome em letra cursiva atravessando o meio
  (o nome fica sobre uma barra fina da base, então nunca solta).
- Pata de pet com nome: pata (almofada + 4 dedos) com o nome do pet em relevo.

Base na cor 1, nome na cor 2, impresso deitado (sem suporte).
"""

from typing import Annotated, ClassVar

import trimesh
from pydantic import BaseModel, Field, StringConstraints

from print3d_mesh.parametric.base import ParametricModel
from print3d_mesh.parametric.fonts import FONTS, scad_font_uses
from print3d_mesh.parametric.openscad import scad_string
from print3d_mesh.parametric.text import TEXT_PATTERN, FontKey, fit_size, legibility_issue

Name = Annotated[str, StringConstraints(min_length=1, max_length=14, pattern=TEXT_PATTERN)]


class FlakeParams(BaseModel):
    name: Name = Field(default="Aline", title="Nome", description="até 14 letras")
    size_mm: float = Field(default=85, ge=60, le=120, title="Diâmetro (mm)")
    thickness_mm: float = Field(default=3, ge=2.4, le=5, title="Espessura (mm)")
    relief_mm: float = Field(default=1.2, ge=0.6, le=2.0, title="Relevo do nome (mm)")
    font: FontKey = Field(default="cursiva", title="Fonte do nome")
    min_text_mm: float = Field(default=4.0, ge=2.0, le=8.0, title="Altura mínima legível (mm)")

    def name_size(self) -> float:
        return fit_size(self.name, self.size_mm * 0.74, self.size_mm * 0.24, self.font)


class SnowflakeName(ParametricModel[FlakeParams]):
    slug = "enfeite-floco-nome"
    title = "Enfeite floco de neve com nome"
    niche = "datas-comemorativas"
    description = "Aro com borda de floco de neve e o nome no meio, argola para fita. Vende em kit."
    params_model = FlakeParams
    text_fields: ClassVar[tuple[str, ...]] = ("name",)

    def parts(self, params: FlakeParams) -> list[str]:
        return ["base", "nome"]

    def scad(self, params: FlakeParams, part: str) -> str:
        return "\n".join(
            [
                scad_font_uses(),
                "$fn = 72;",
                f"PART = {scad_string(part)};",
                f"D = {params.size_mm};",
                f"T = {params.thickness_mm};",
                f"REL = {params.relief_mm};",
                f"N = {scad_string(params.name)};",
                f"NS = {params.name_size():.2f};",
                f"F = {scad_string(FONTS[params.font].scad_name)};",
                _FLAKE_SCAD,
            ]
        )

    def check(self, params: FlakeParams, meshes: dict[str, trimesh.Trimesh]) -> list[str]:
        issue = legibility_issue("o nome", params.name_size(), params.min_text_mm)
        return [issue] if issue else []


_FLAKE_SCAD = """
R = D / 2;
W = D * 0.07;  // largura do aro
module arm(len) {  // braço de floco na borda: haste + duas pontas em V
    translate([-1.2, 0]) square([2.4, len]);
    translate([0, len * 0.55]) rotate(40) translate([-1.1, 0]) square([2.2, len * 0.45]);
    translate([0, len * 0.55]) rotate(-40) translate([-1.1, 0]) square([2.2, len * 0.45]);
}
module rim2d() {
    difference() { circle(r = R - W * 0.2); circle(r = R - W); }
    for (a = [0 : 30 : 359]) rotate(a) translate([0, R - W * 0.9]) arm(W * 1.4);
}
module ring2d() difference() {
    union() {
        translate([0, R + W * 0.5]) circle(r = 4.5);
        translate([-2.5, R - W]) square([5, W * 1.5]);
    }
    translate([0, R + W * 0.5]) circle(r = 2);
}
module name2d() text(N, size = NS, font = F, halign = "center", valign = "center");
module bar2d() translate([-(R - W * 0.6), -NS * 0.18]) square([2 * (R - W * 0.6), NS * 0.36]);

if (PART == "base")
    linear_extrude(T) union() { rim2d(); ring2d(); bar2d(); offset(r = 1.2) name2d(); }
if (PART == "nome") translate([0, 0, T]) linear_extrude(REL) name2d();
"""


class PawParams(BaseModel):
    name: Name = Field(default="Luna", title="Nome do pet", description="até 14 letras")
    size_mm: float = Field(default=75, ge=50, le=110, title="Altura (mm)")
    thickness_mm: float = Field(default=3.5, ge=2.4, le=5, title="Espessura (mm)")
    relief_mm: float = Field(default=1.2, ge=0.6, le=2.0, title="Relevo do nome (mm)")
    font: FontKey = Field(default="cursiva", title="Fonte do nome")
    min_text_mm: float = Field(default=4.0, ge=2.0, le=8.0, title="Altura mínima legível (mm)")

    def name_size(self) -> float:
        return fit_size(self.name, self.size_mm * 0.62, self.size_mm * 0.2, self.font)


class PetPawName(ParametricModel[PawParams]):
    slug = "enfeite-pata-nome"
    title = "Enfeite pata de pet com nome"
    niche = "datas-comemorativas"
    description = "Patinha com o nome do pet em relevo e argola para fita."
    params_model = PawParams
    text_fields: ClassVar[tuple[str, ...]] = ("name",)

    def parts(self, params: PawParams) -> list[str]:
        return ["base", "nome"]

    def scad(self, params: PawParams, part: str) -> str:
        return "\n".join(
            [
                scad_font_uses(),
                "$fn = 72;",
                f"PART = {scad_string(part)};",
                f"H = {params.size_mm};",
                f"T = {params.thickness_mm};",
                f"REL = {params.relief_mm};",
                f"N = {scad_string(params.name)};",
                f"NS = {params.name_size():.2f};",
                f"F = {scad_string(FONTS[params.font].scad_name)};",
                _PAW_SCAD,
            ]
        )

    def check(self, params: PawParams, meshes: dict[str, trimesh.Trimesh]) -> list[str]:
        issue = legibility_issue("o nome", params.name_size(), params.min_text_mm)
        return [issue] if issue else []


_PAW_SCAD = """
module pad() translate([0, -H * 0.16]) scale([1, 0.78]) circle(d = H * 0.72);
TOES = [[-H * 0.31, H * 0.14], [-H * 0.11, H * 0.3], [H * 0.11, H * 0.3], [H * 0.31, H * 0.14]];
module toes() for (p = TOES)
    translate(p) scale([0.8, 1]) circle(d = H * 0.26);
module paw2d() offset(r = 2) offset(delta = -2) union() {
    pad(); toes();
    // pontes finas: dedos e almofada viram uma peça só
    for (p = TOES) translate([p[0] - 1.5, -H * 0.1]) square([3, H * 0.3]);
}
module ring2d() difference() {
    union() {
        translate([0, H * 0.47]) circle(r = 4.5);
        translate([-2.5, H * 0.3]) square([5, H * 0.17]);
    }
    translate([0, H * 0.47]) circle(r = 2);
}
module name2d()
    translate([0, -H * 0.17]) text(N, size = NS, font = F, halign = "center", valign = "center");

if (PART == "base") linear_extrude(T) union() { paw2d(); ring2d(); }
if (PART == "nome") translate([0, 0, T]) linear_extrude(REL) name2d();
"""
