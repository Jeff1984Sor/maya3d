"""Gerador de caixas (spec 2.7): um modelo, centenas de combinações.

Medidas são INTERNAS (o que cabe dentro). Tampa de encaixe impressa de cabeça para baixo:
placa + aba que entra na caixa, com folga calibrada por material.
Próximas variações (registradas em docs/fases/fase-2.md): coração, rosca, deslizante,
dobradiça impressa e ímã.
"""

from typing import Annotated, Literal, Self

import trimesh
from pydantic import BaseModel, Field, StringConstraints, model_validator

from print3d_mesh.parametric.base import ParametricModel
from print3d_mesh.parametric.fonts import FONTS, scad_font_uses
from print3d_mesh.parametric.openscad import scad_string

Shape = Literal["redonda", "quadrada", "retangular", "hexagonal", "oval"]
Lid = Literal["sem_tampa", "encaixe"]
FontKey = Literal["bold", "semibold", "condensada", "cursiva", "retro", "manuscrita"]


class BoxParams(BaseModel):
    shape: Shape = Field(default="redonda", title="Formato")
    width_mm: float = Field(default=60, ge=20, le=250, title="Largura/diâmetro interno (mm)")
    depth_mm: float = Field(
        default=60,
        ge=20,
        le=250,
        title="Profundidade interna (mm)",
        description="só retangular e oval",
    )
    height_mm: float = Field(default=30, ge=10, le=250, title="Altura interna (mm)")
    wall_mm: float = Field(default=2.0, ge=1.2, le=4.0, title="Parede (mm)")
    bottom_mm: float = Field(default=2.0, ge=1.2, le=4.0, title="Fundo (mm)")
    corner_radius_mm: float = Field(default=3.0, ge=0, le=15, title="Raio dos cantos (mm)")
    lid: Lid = Field(default="encaixe", title="Tampa")
    lid_mm: float = Field(default=2.0, ge=1.6, le=4.0, title="Espessura da tampa (mm)")
    lip_mm: float = Field(default=6.0, ge=3.0, le=15.0, title="Aba de encaixe (mm)")
    clearance_mm: float = Field(
        default=0.25,
        ge=0.1,
        le=0.6,
        title="Folga da tampa (mm)",
        description="calibre por material após teste de encaixe",
    )
    dividers_x: int = Field(default=0, ge=0, le=6, title="Divisórias no comprimento")
    dividers_y: int = Field(default=0, ge=0, le=6, title="Divisórias na largura")
    lid_text: Annotated[str, StringConstraints(max_length=20)] | None = Field(
        default=None, title="Texto na tampa"
    )
    text_font: FontKey = Field(default="semibold", title="Fonte do texto")
    text_depth_mm: float = Field(default=0.8, ge=0.4, le=1.5, title="Profundidade do texto (mm)")

    @model_validator(mode="after")
    def _consistente(self) -> Self:
        if self.shape in ("redonda", "quadrada", "hexagonal"):
            self.depth_mm = self.width_mm
        if self.corner_radius_mm * 2 >= min(self.width_mm, self.depth_mm):
            raise ValueError("raio do canto grande demais para as medidas")
        if self.lid == "encaixe" and self.lip_mm >= self.height_mm:
            raise ValueError("aba da tampa maior que a altura da caixa")
        if self.lid_text and self.lid == "sem_tampa":
            raise ValueError("texto na tampa exige tampa")
        return self

    @property
    def outer_mm(self) -> tuple[float, float, float]:
        lid_extra = self.lid_mm if self.lid == "encaixe" else 0
        return (
            self.width_mm + 2 * self.wall_mm,
            self.depth_mm + 2 * self.wall_mm,
            self.bottom_mm + self.height_mm + lid_extra,
        )


class ParametricBox(ParametricModel[BoxParams]):
    slug = "caixa"
    title = "Caixa paramétrica"
    niche = "caixas"
    description = "Caixa com medidas internas, tampa de encaixe, divisórias e texto na tampa."
    params_model = BoxParams

    def parts(self, params: BoxParams) -> list[str]:
        return ["caixa"] if params.lid == "sem_tampa" else ["caixa", "tampa"]

    def scad(self, params: BoxParams, part: str) -> str:
        lines = [
            scad_font_uses(),
            "$fn = 96;",
            f"PART = {scad_string(part)};",
            f"SHAPE = {scad_string(params.shape)};",
            f"W = {params.width_mm}; D = {params.depth_mm}; H = {params.height_mm};",
            f"WALL = {params.wall_mm}; BOTTOM = {params.bottom_mm}; R = {params.corner_radius_mm};",
            f"LID_T = {params.lid_mm}; LIP = {params.lip_mm}; CLEAR = {params.clearance_mm};",
            f"HAS_LID = {'true' if params.lid == 'encaixe' else 'false'};",
            f"DX = {params.dividers_x}; DY = {params.dividers_y};",
            f"TXT = {scad_string(params.lid_text or '')};",
            f"TF = {scad_string(FONTS[params.text_font].scad_name)};",
            f"TXT_D = {params.text_depth_mm};",
            _BOX_SCAD,
        ]
        return "\n".join(lines)

    def check(self, params: BoxParams, meshes: dict[str, trimesh.Trimesh]) -> list[str]:
        issues: list[str] = []
        box = meshes.get("caixa")
        if box is not None:
            ox, oy, _ = params.outer_mm
            if abs(sorted(box.extents[:2])[1] - max(ox, oy)) > 1.0:
                issues.append("medida externa da caixa diferente do esperado")
        return issues


_BOX_SCAD = """
LIP_WALL = 1.6;
DIV_T = 1.2;

module inner2d() {
    if (SHAPE == "redonda") circle(d = W);
    else if (SHAPE == "hexagonal") circle(d = W, $fn = 6);
    else if (SHAPE == "oval") scale([1, D / W]) circle(d = W);
    else offset(r = R) square([W - 2 * R, D - 2 * R], center = true);
}
module outer2d() offset(r = WALL) inner2d();

module dividers(h) intersection() {
    linear_extrude(h) inner2d();
    union() {
        if (DX > 0) for (i = [1 : DX])
            translate([-W / 2 + i * W / (DX + 1) - DIV_T / 2, -D / 2, 0]) cube([DIV_T, D, h]);
        if (DY > 0) for (j = [1 : DY])
            translate([-W / 2, -D / 2 + j * D / (DY + 1) - DIV_T / 2, 0]) cube([W, DIV_T, h]);
    }
}

module box() {
    difference() {
        linear_extrude(BOTTOM + H) outer2d();
        translate([0, 0, BOTTOM]) linear_extrude(H + 1) inner2d();
    }
    // divisórias param abaixo da aba da tampa
    div_h = HAS_LID ? H - LIP - 1 : H;
    if (DX + DY > 0) translate([0, 0, BOTTOM]) dividers(div_h);
}

// Tampa impressa de cabeça para baixo: placa em z=0 (face de cima depois de virar) + aba.
module lid() {
    difference() {
        union() {
            linear_extrude(LID_T) outer2d();
            translate([0, 0, LID_T]) linear_extrude(LIP) difference() {
                offset(delta = -CLEAR) inner2d();
                offset(delta = -CLEAR - LIP_WALL) inner2d();
            }
        }
        if (len(TXT) > 0) translate([0, 0, -0.01]) linear_extrude(TXT_D)
            mirror([1, 0, 0]) resize([min(W, D) * 0.8, 0], auto = true)
                text(TXT, size = 10, font = TF, halign = "center", valign = "center");
    }
}

if (PART == "caixa") box();
if (PART == "tampa" && HAS_LID) lid();
"""
