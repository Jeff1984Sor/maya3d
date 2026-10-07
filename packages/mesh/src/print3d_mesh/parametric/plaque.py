"""Placas e lembrancinhas com texto (brindes, datas comemorativas, decoração).

- Placa com nome: porta, mesa, escritório, quarto infantil. 1 ou 2 linhas, moldura opcional,
  furos para parafuso/fita dupla-face ou pé de encaixe.
- Lembrancinha (tag): medalhão de festa (coração, círculo, estrela) com nome e detalhe
  ("1 aninho", data), argola para fita.

Base na cor 1, texto e moldura na cor 2 (relevo), impressa deitada.
"""

from typing import Annotated, ClassVar, Literal, Self

import trimesh
from pydantic import BaseModel, Field, StringConstraints, model_validator

from print3d_mesh.parametric.base import ParametricModel
from print3d_mesh.parametric.fonts import FONTS, scad_font_uses
from print3d_mesh.parametric.openscad import scad_string
from print3d_mesh.parametric.text import (
    TEXT_PATTERN,
    FontKey,
    fit_size,
    legibility_issue,
    overflow_issue,
)

PlaqueShape = Literal["retangular", "arredondada", "oval"]
Mount = Literal["furos", "pe", "nenhum"]
TagShape = Literal["coracao", "circulo", "estrela"]
Line = Annotated[str, StringConstraints(min_length=1, max_length=24, pattern=TEXT_PATTERN)]


class PlaqueParams(BaseModel):
    line1: Line = Field(default="Sala da Ana", title="Texto principal", description="até 24")
    line2: Line | None = Field(default=None, title="Segunda linha (opcional)")
    width_mm: float = Field(default=160, ge=60, le=250, title="Largura (mm)")
    shape: PlaqueShape = Field(default="arredondada", title="Formato")
    thickness_mm: float = Field(default=4, ge=3, le=8, title="Espessura (mm)")
    relief_mm: float = Field(default=1.0, ge=0.6, le=2.0, title="Relevo (mm)")
    frame: bool = Field(default=True, title="Moldura")
    mount: Mount = Field(default="furos", title="Fixação")
    font: FontKey = Field(default="bold", title="Fonte do texto principal")
    font2: FontKey = Field(default="semibold", title="Fonte da segunda linha")
    min_text_mm: float = Field(default=3.5, ge=2.0, le=8.0, title="Altura mínima legível (mm)")

    @property
    def height_mm(self) -> float:
        return round(self.width_mm * (0.42 if self.line2 else 0.32), 2)

    @property
    def text_room(self) -> float:
        side = 18 if self.mount == "furos" else 8
        return self.width_mm - 2 * side

    def size1(self) -> float:
        cap = self.height_mm * (0.3 if self.line2 else 0.42)
        return fit_size(self.line1, self.text_room, cap, self.font)

    def size2(self) -> float:
        return fit_size(self.line2 or "", self.text_room, self.height_mm * 0.17, self.font2)


class PlaqueWithName(ParametricModel[PlaqueParams]):
    slug = "placa-nome"
    title = "Placa com nome"
    niche = "brindes"
    description = "Placa de porta ou mesa com 1 ou 2 linhas, moldura e fixação à escolha."
    params_model = PlaqueParams
    text_fields: ClassVar[tuple[str, ...]] = ("line1", "line2")

    def parts(self, params: PlaqueParams) -> list[str]:
        return ["placa", "texto", *(["pe"] if params.mount == "pe" else [])]

    def scad(self, params: PlaqueParams, part: str) -> str:
        two = bool(params.line2)
        return "\n".join(
            [
                scad_font_uses(),
                "$fn = 72;",
                f"PART = {scad_string(part)};",
                f"W = {params.width_mm};",
                f"H = {params.height_mm};",
                f"T = {params.thickness_mm};",
                f"REL = {params.relief_mm};",
                f"SHAPE = {scad_string(params.shape)};",
                f"L1 = {scad_string(params.line1)};",
                f"L2 = {scad_string(params.line2 or '')};",
                f"S1 = {params.size1()};",
                f"S2 = {params.size2()};",
                f"Y1 = {params.height_mm * 0.14 if two else 0:.2f};",
                f"Y2 = {-params.height_mm * 0.22:.2f};",
                f"F1 = {scad_string(FONTS[params.font].scad_name)};",
                f"F2 = {scad_string(FONTS[params.font2].scad_name)};",
                f"FRAME = {'true' if params.frame else 'false'};",
                f"HOLES = {'true' if params.mount == 'furos' else 'false'};",
                _PLAQUE_SCAD,
            ]
        )

    def check(self, params: PlaqueParams, meshes: dict[str, trimesh.Trimesh]) -> list[str]:
        issues = [
            i
            for i in (
                legibility_issue("o texto principal", params.size1(), params.min_text_mm),
                legibility_issue("a segunda linha", params.size2(), params.min_text_mm)
                if params.line2
                else None,
            )
            if i
        ]
        text = meshes.get("texto")
        if text is not None and not params.frame:
            issue = overflow_issue("o texto", float(text.extents[0]), params.text_room)
            if issue:
                issues.append(issue)
        return issues


_PLAQUE_SCAD = """
module shape2d() {
    if (SHAPE == "retangular") square([W, H], center = true);
    if (SHAPE == "arredondada")
        offset(r = H * 0.18) square([W - H * 0.36, H - H * 0.36], center = true);
    if (SHAPE == "oval") scale([W / H, 1]) circle(d = H);
}

module plate2d() difference() {
    shape2d();
    if (HOLES) for (s = [-1, 1]) translate([s * (W / 2 - 9), 0]) circle(r = 2.2);
}

module text2d() {
    translate([0, Y1]) text(L1, size = S1, font = F1, halign = "center", valign = "center");
    if (len(L2) > 0)
        translate([0, Y2]) text(L2, size = S2, font = F2, halign = "center", valign = "center");
}

module frame2d() difference() { offset(delta = -3) shape2d(); offset(delta = -5) shape2d(); }

module foot() {
    d = 34; w = W * 0.5; h = 12;
    translate([0, -H / 2 - d / 2 - 10, 0]) difference() {
        translate([-w / 2, -d / 2, 0]) cube([w, d, h]);
        translate([-w / 2 - 1, -(T + 0.3) / 2, 2]) cube([w + 2, T + 0.3, h]);
    }
}

if (PART == "placa") linear_extrude(T) plate2d();
if (PART == "texto") translate([0, 0, T]) linear_extrude(REL) { text2d(); if (FRAME) frame2d(); }
if (PART == "pe") foot();
"""


class TagParams(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=14, pattern=TEXT_PATTERN)] = (
        Field(default="Helena", title="Nome")
    )
    detail: Annotated[str, StringConstraints(max_length=18, pattern=TEXT_PATTERN)] | None = Field(
        default="1 aninho", title="Detalhe (opcional)", description="idade, data, frase curta"
    )
    shape: TagShape = Field(default="coracao", title="Formato")
    size_mm: float = Field(default=50, ge=35, le=80, title="Tamanho (mm)")
    thickness_mm: float = Field(default=3, ge=2, le=5, title="Espessura (mm)")
    relief_mm: float = Field(default=0.8, ge=0.6, le=1.5, title="Relevo (mm)")
    ribbon_hole: bool = Field(default=True, title="Argola para fita")
    font: FontKey = Field(default="cursiva", title="Fonte do nome")
    min_text_mm: float = Field(default=3.0, ge=2.0, le=8.0, title="Altura mínima legível (mm)")

    @model_validator(mode="after")
    def _limpo(self) -> Self:
        if self.detail is not None and not self.detail.strip():
            self.detail = None
        return self

    @property
    def room(self) -> float:
        return self.size_mm * {"estrela": 0.5, "coracao": 0.62, "circulo": 0.78}[self.shape]

    def name_size(self) -> float:
        return fit_size(self.name, self.room, self.size_mm * 0.22, self.font)

    def detail_size(self) -> float:
        return fit_size(self.detail or "", self.room * 0.9, self.size_mm * 0.11, "semibold")


class PartyTag(ParametricModel[TagParams]):
    slug = "lembrancinha-tag"
    title = "Lembrancinha (tag)"
    niche = "datas-comemorativas"
    description = "Medalhão de festa com nome e detalhe, argola para fita. Vende em kit."
    params_model = TagParams
    text_fields: ClassVar[tuple[str, ...]] = ("name", "detail")

    def parts(self, params: TagParams) -> list[str]:
        return ["base", "texto"]

    def scad(self, params: TagParams, part: str) -> str:
        has_detail = bool(params.detail)
        return "\n".join(
            [
                scad_font_uses(),
                "$fn = 72;",
                f"PART = {scad_string(part)};",
                f"D = {params.size_mm};",
                f"T = {params.thickness_mm};",
                f"REL = {params.relief_mm};",
                f"SHAPE = {scad_string(params.shape)};",
                f"N = {scad_string(params.name)};",
                f"X = {scad_string(params.detail or '')};",
                f"NS = {params.name_size()};",
                f"XS = {params.detail_size()};",
                f"NY = {params.size_mm * (0.06 if has_detail else -0.02):.2f};",
                f"XY = {-params.size_mm * 0.2:.2f};",
                f"F = {scad_string(FONTS[params.font].scad_name)};",
                f"XF = {scad_string(FONTS['semibold'].scad_name)};",
                f"RING = {'true' if params.ribbon_hole else 'false'};",
                _TAG_SCAD,
            ]
        )

    def check(self, params: TagParams, meshes: dict[str, trimesh.Trimesh]) -> list[str]:
        issues = [
            i
            for i in (
                legibility_issue("o nome", params.name_size(), params.min_text_mm),
                legibility_issue("o detalhe", params.detail_size(), params.min_text_mm)
                if params.detail
                else None,
            )
            if i
        ]
        base = meshes.get("base")
        if base is not None and len(base.split(only_watertight=False)) > 1:
            issues.append("a base ficou em mais de um pedaço")
        return issues


_TAG_SCAD = """
module heart(d) resize([d, 0], auto = true) rotate(45) union() {
    square(10, center = true);
    translate([0, 5]) circle(d = 10);
    translate([5, 0]) circle(d = 10);
}

module star(d) polygon([for (i = [0:9]) let(r = (i % 2 == 0) ? d / 2 : d * 0.24)
    [r * sin(i * 36), r * cos(i * 36)]]);

module shape2d() {
    if (SHAPE == "coracao") translate([0, -D * 0.04]) heart(D);
    if (SHAPE == "circulo") circle(d = D);
    if (SHAPE == "estrela") star(D * 1.12);
}

module tag2d() difference() {
    union() {
        shape2d();
        if (RING) {
            translate([0, D / 2 + 1.5]) circle(r = 4.5);
            translate([-2.5, 0]) square([5, D / 2 + 1.5]);  // liga a argola ao corpo
        }
    }
    if (RING) translate([0, D / 2 + 1.5]) circle(r = 2);
}

module text2d() {
    translate([0, NY]) text(N, size = NS, font = F, halign = "center", valign = "center");
    if (len(X) > 0)
        translate([0, XY]) text(X, size = XS, font = XF, halign = "center", valign = "center");
}

if (PART == "base") linear_extrude(T) tag2d();
if (PART == "texto") translate([0, 0, T]) linear_extrude(REL) text2d();
"""
