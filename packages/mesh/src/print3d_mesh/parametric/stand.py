"""Suporte de celular de mesa (celular).

O perfil lateral (base + encosto inclinado + aba da frente + reforço) é extrudado na largura
e a peça imprime DEITADA de lado: sem suporte e com as camadas no sentido mais forte.
A fenda entre a aba e o encosto é a espessura do celular com capinha + folga; opção de
passagem de cabo no meio da aba.
"""

import math
from typing import Self

import trimesh
from pydantic import BaseModel, Field, model_validator

from print3d_mesh.parametric.base import ParametricModel
from print3d_mesh.parametric.openscad import scad_string

WALL = 5.0


class StandParams(BaseModel):
    angle_deg: float = Field(default=65, ge=50, le=80, title="Inclinação (graus)")
    phone_mm: float = Field(default=12, ge=7, le=20, title="Espessura do celular com capa (mm)")
    width_mm: float = Field(default=70, ge=50, le=120, title="Largura (mm)")
    back_mm: float = Field(default=85, ge=60, le=140, title="Altura do encosto (mm)")
    lip_mm: float = Field(default=12, ge=8, le=25, title="Altura da aba da frente (mm)")
    cable_slot: bool = Field(default=True, title="Passagem de cabo")

    @model_validator(mode="after")
    def _cabe(self) -> Self:
        if self.cable_slot and self.width_mm < 55:
            raise ValueError("com passagem de cabo, a largura mínima é 55 mm")
        return self

    @property
    def gap(self) -> float:
        return self.phone_mm + 1.0  # folga para entrar e sair fácil

    @property
    def base_mm(self) -> float:
        reach = self.back_mm * math.cos(math.radians(self.angle_deg))
        return round(WALL + self.gap + reach + WALL * 2, 2)


class PhoneStand(ParametricModel[StandParams]):
    slug = "suporte-celular"
    title = "Suporte de celular"
    niche = "celular"
    description = "Suporte de mesa sob medida para o celular com capinha; passagem de cabo."
    params_model = StandParams

    def parts(self, params: StandParams) -> list[str]:
        return ["suporte"]

    def scad(self, params: StandParams, part: str) -> str:
        return "\n".join(
            [
                "$fn = 48;",
                f"PART = {scad_string(part)};",
                f"WALL = {WALL};",
                f"A = {params.angle_deg};",
                f"GAP = {params.gap};",
                f"W = {params.width_mm};",
                f"BACK = {params.back_mm};",
                f"LIP = {params.lip_mm};",
                f"BASE = {params.base_mm};",
                f"CABLE = {'true' if params.cable_slot else 'false'};",
                _STAND_SCAD,
            ]
        )

    def check(self, params: StandParams, meshes: dict[str, trimesh.Trimesh]) -> list[str]:
        mesh = meshes.get("suporte")
        if mesh is not None and len(mesh.split(only_watertight=False)) > 1:
            return ["o suporte ficou em mais de um pedaço"]
        return []


_STAND_SCAD = """
// Perfil no plano XY (X = frente → trás, Y = altura); extrudado W em Z (imprime de lado).
module rest2d() translate([WALL + GAP, 0]) rotate(-(90 - A)) square([WALL, BACK]);

module profile2d() intersection() {
    translate([0, 0]) square([BASE * 3, BACK * 2]);  // nada abaixo da mesa
    profile_raw();
}

module profile_raw() union() {
    square([BASE, WALL]);                       // base
    square([WALL, WALL + LIP]);                 // aba da frente
    rest2d();                                   // encosto inclinado
    hull() {                                    // reforço: encosto até o fim da base
        intersection() { rest2d(); translate([0, BACK * 0.45]) square([BASE * 2, WALL]); }
        translate([BASE - WALL, 0]) square([WALL, WALL]);
    }
}

difference() {
    linear_extrude(W) profile2d();
    if (CABLE) translate([-1, -1, W / 2 - 6]) cube([WALL + GAP + 2, WALL + LIP + 2, 12]);
}
"""
