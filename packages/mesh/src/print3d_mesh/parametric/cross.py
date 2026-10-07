"""Cruz personalizada (religioso): batizado, primeira comunhão, crisma, lembrança.

Placa em cruz latina impressa deitada (sem suporte), nome em relevo no braço e data opcional
ao longo da haste, em segunda cor. Acabamento: furo para pendurar ou pé de encaixe (peça
separada com fenda, impressa ao lado).
"""

from typing import Annotated, ClassVar, Literal

import trimesh
from pydantic import BaseModel, Field, StringConstraints

from print3d_mesh.parametric.base import ParametricModel
from print3d_mesh.parametric.fonts import FONTS, scad_font_uses
from print3d_mesh.parametric.openscad import scad_string
from print3d_mesh.parametric.text import (
    DATE_PATTERN,
    TEXT_PATTERN,
    FontKey,
    fit_size,
    legibility_issue,
    overflow_issue,
)

Finish = Literal["pendurar", "pe", "nenhum"]
Edge = Literal["reta", "arredondada"]


class CrossParams(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=16, pattern=TEXT_PATTERN)] = (
        Field(default="Miguel", title="Nome", description="até 16 caracteres")
    )
    date: Annotated[str, StringConstraints(pattern=DATE_PATTERN)] | None = Field(
        default=None, title="Data (opcional)", description="ex.: 12/10/2026"
    )
    height_mm: float = Field(default=150, ge=80, le=250, title="Altura (mm)")
    thickness_mm: float = Field(default=5, ge=3, le=10, title="Espessura (mm)")
    relief_mm: float = Field(default=1.0, ge=0.6, le=2.0, title="Relevo do texto (mm)")
    edge: Edge = Field(default="arredondada", title="Cantos")
    finish: Finish = Field(default="pe", title="Acabamento")
    font: FontKey = Field(default="cursiva", title="Fonte")
    min_text_mm: float = Field(default=3.5, ge=2.0, le=8.0, title="Altura mínima legível (mm)")

    @property
    def bar(self) -> float:
        return self.height_mm * 0.17

    @property
    def arm(self) -> float:
        return self.height_mm * 0.62

    @property
    def cross_y(self) -> float:
        return self.height_mm * 0.68

    def name_size(self) -> float:
        return fit_size(self.name, self.arm - 6, self.bar * 0.62, self.font)

    def date_size(self) -> float:
        room = self.cross_y - self.bar / 2 - 8
        return fit_size(self.date or "", room, self.bar * 0.45, "semibold")


class CrossWithName(ParametricModel[CrossParams]):
    slug = "cruz-nome"
    title = "Cruz com nome"
    niche = "religioso"
    description = "Cruz com nome (e data) em relevo; de pendurar ou com pé de encaixe."
    params_model = CrossParams
    text_fields: ClassVar[tuple[str, ...]] = ("name", "date")

    def parts(self, params: CrossParams) -> list[str]:
        return ["cruz", "texto", *(["pe"] if params.finish == "pe" else [])]

    def scad(self, params: CrossParams, part: str) -> str:
        return "\n".join(
            [
                scad_font_uses(),
                "$fn = 64;",
                f"PART = {scad_string(part)};",
                f"H = {params.height_mm};",
                f"T = {params.thickness_mm};",
                f"REL = {params.relief_mm};",
                f"B = {params.bar:.2f};",
                f"ARM = {params.arm:.2f};",
                f"CY = {params.cross_y:.2f};",
                f"N = {scad_string(params.name)};",
                f"NS = {params.name_size()};",
                f"D = {scad_string(params.date or '')};",
                f"DS = {params.date_size()};",
                f"F = {scad_string(FONTS[params.font].scad_name)};",
                f"DF = {scad_string(FONTS['semibold'].scad_name)};",
                f"ROUND = {'true' if params.edge == 'arredondada' else 'false'};",
                f"HANG = {'true' if params.finish == 'pendurar' else 'false'};",
                _CROSS_SCAD,
            ]
        )

    def check(self, params: CrossParams, meshes: dict[str, trimesh.Trimesh]) -> list[str]:
        issues = [
            i
            for i in (
                legibility_issue("o nome", params.name_size(), params.min_text_mm),
                legibility_issue("a data", params.date_size(), params.min_text_mm)
                if params.date
                else None,
            )
            if i
        ]
        cross, text = meshes.get("cruz"), meshes.get("texto")
        if cross is not None and len(cross.split(only_watertight=False)) > 1:
            issues.append("a cruz ficou em mais de um pedaço")
        if text is not None:
            issue = overflow_issue("o nome", float(text.extents[0]), params.arm)
            if issue:
                issues.append(issue)
        return issues


_CROSS_SCAD = """
module shape2d() {
    r = ROUND ? B * 0.18 : 0;
    offset(r = r) offset(delta = -r) union() {
        translate([-B / 2, 0]) square([B, H]);
        translate([-ARM / 2, CY - B / 2]) square([ARM, B]);
    }
}

module cross2d() difference() {
    shape2d();
    if (HANG) translate([0, H - B * 0.45]) circle(r = 2.5);
}

module text2d() {
    translate([0, CY]) text(N, size = NS, font = F, halign = "center", valign = "center");
    if (len(D) > 0)
        translate([0, (CY - B / 2) / 2 + 2]) rotate(90)
            text(D, size = DS, font = DF, halign = "center", valign = "center");
}

// Pé: bloco com fenda na espessura da cruz (+0,3 mm de folga), impresso ao lado.
module foot() {
    w = ARM * 0.9; d = max(T * 6, 30); h = B * 0.9;
    translate([ARM / 2 + d / 2 + 10, H / 2, 0]) difference() {
        translate([-d / 2, -w / 2, 0]) cube([d, w, h]);
        translate([-(T + 0.3) / 2, -B / 2 - 0.15, 2]) cube([T + 0.3, B + 0.3, h]);
    }
}

if (PART == "cruz") linear_extrude(T) cross2d();
if (PART == "texto") translate([0, 0, T]) linear_extrude(REL) text2d();
if (PART == "pe") foot();
"""
