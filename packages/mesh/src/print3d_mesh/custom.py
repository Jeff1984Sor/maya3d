"""Peça sob medida escrita pela IA do painel em OpenSCAD (quando não há modelo paramétrico).

O código vem da IA, então é tratado como não confiável:
- nada de ler arquivos (include/use/import/surface) — as fontes permitidas somos nós que
  registramos; só os nomes de fonte da lista valem;
- tamanho e número de partes limitados; o OpenSCAD roda no worker com limite de tempo;
- os textos de `text("...")` são devolvidos para o Guardião conferir antes de gerar.
Medidas, volume e problemas vêm da malha gerada, nunca da IA.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import trimesh

from print3d_mesh.analysis import mesh_report
from print3d_mesh.parametric.fonts import FONTS, scad_font_uses
from print3d_mesh.parametric.openscad import OpenScadRunner

MAX_PARTS = 4
MAX_SOURCE_CHARS = 12_000
PART_NAME = re.compile(r"^[a-z0-9_]{1,24}$")
_FORBIDDEN = re.compile(r"\b(include|use)\s*<|\b(import|surface)\s*\(", re.IGNORECASE)
_TEXT_LITERAL = re.compile(r"\btext\s*\(\s*(?:text\s*=\s*)?\"((?:[^\"\\]|\\.)*)\"")
_FONT_ARG = re.compile(r"\bfont\s*=\s*\"([^\"]*)\"")
FONT_NAMES = frozenset(f.scad_name for f in FONTS.values())


class CustomScadError(Exception):
    pass


@dataclass(frozen=True)
class CustomPart:
    name: str  # vira o arquivo <nome>.stl (ex.: base, texto)
    scad: str


def validate(parts: list[CustomPart]) -> list[str]:
    """Confere o código e devolve os textos que a peça escreve (para o Guardião)."""
    if not 1 <= len(parts) <= MAX_PARTS:
        raise CustomScadError(f"use de 1 a {MAX_PARTS} partes")
    names = [p.name for p in parts]
    if len(set(names)) != len(names) or not all(PART_NAME.match(n) for n in names):
        raise CustomScadError("nomes de parte: minúsculas, números e _ (sem repetir)")
    texts: list[str] = []
    for part in parts:
        if len(part.scad) > MAX_SOURCE_CHARS:
            raise CustomScadError(f"parte {part.name}: código grande demais")
        if _FORBIDDEN.search(part.scad):
            raise CustomScadError(
                f"parte {part.name}: não use include/use/import/surface (sem ler arquivos)"
            )
        for font in _FONT_ARG.findall(part.scad):
            if font not in FONT_NAMES:
                raise CustomScadError(
                    f"parte {part.name}: fonte {font!r} não permitida; use {sorted(FONT_NAMES)}"
                )
        texts += [t for t in _TEXT_LITERAL.findall(part.scad) if t.strip()]
    return texts


def generate_custom(
    parts: list[CustomPart], out_dir: Path, runner: OpenScadRunner | None = None
) -> dict[str, Any]:
    """Gera cada parte (STL), o conjunto (completo.stl) e o projeto .3mf com uma peça por parte."""
    validate(parts)
    runner = runner or OpenScadRunner(timeout_s=90)
    out_dir.mkdir(parents=True, exist_ok=True)
    header = f"{scad_font_uses()}\n$fn = 64;\n"
    meshes: dict[str, trimesh.Trimesh] = {}
    files: dict[str, str] = {}
    for part in parts:
        path = runner.render(header + part.scad, out_dir / f"{part.name}.stl")
        mesh = trimesh.load(path, force="mesh")
        if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
            raise CustomScadError(f"parte {part.name} ficou vazia (nada foi desenhado)")
        meshes[part.name] = mesh
        files[part.name] = path.name
    reports = {name: mesh_report(mesh) for name, mesh in meshes.items()}
    issues = [f"{name}: {i}" for name, r in reports.items() for i in r.issues]
    combined = trimesh.util.concatenate(list(meshes.values()))
    combined.export(out_dir / "completo.stl")  # type: ignore[no-untyped-call]
    if float(combined.bounds[0][2]) < -0.01:
        issues.append("parte da peça está abaixo da mesa (z < 0)")
    scene = trimesh.Scene()
    for name, mesh in meshes.items():  # mesmas coordenadas: o Bambu Studio monta as cores
        scene.add_geometry(mesh, node_name=name, geom_name=name)
    scene.export(out_dir / "projeto.3mf")  # type: ignore[no-untyped-call]
    return {
        "files": files,
        "combined": "completo.stl",
        "project": "projeto.3mf",
        "bbox_mm": [round(float(v), 1) for v in combined.extents],
        "issues": issues,
        "printable": not issues,
        "source": {p.name: p.scad for p in parts},
    }
