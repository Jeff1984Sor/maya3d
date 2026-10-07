"""Gera todas as partes de um modelo, analisa cada uma e monta o STL combinado."""

from pathlib import Path
from typing import Any

import trimesh
from pydantic import BaseModel

from print3d_mesh.analysis import mesh_report
from print3d_mesh.contracts import MeshReport
from print3d_mesh.parametric.base import ParametricModel
from print3d_mesh.parametric.box import ParametricBox
from print3d_mesh.parametric.keychain import KeychainLetterName
from print3d_mesh.parametric.openscad import OpenScadRunner

MODELS: dict[str, ParametricModel[Any]] = {
    m.slug: m for m in (KeychainLetterName(), ParametricBox())
}


class GenerationResult(BaseModel):
    model: str
    params: dict[str, Any]
    files: dict[str, str]  # parte → nome do arquivo STL
    combined: str  # STL com todas as partes (visualização / impressão em uma cor)
    reports: dict[str, MeshReport]
    bbox_mm: tuple[float, float, float]
    issues: list[str]

    @property
    def printable(self) -> bool:
        return not self.issues


def generate(
    model: ParametricModel[Any],
    raw_params: dict[str, Any],
    out_dir: Path,
    runner: OpenScadRunner | None = None,
) -> GenerationResult:
    runner = runner or OpenScadRunner()
    params = model.parse(raw_params)
    out_dir.mkdir(parents=True, exist_ok=True)

    meshes: dict[str, trimesh.Trimesh] = {}
    files: dict[str, str] = {}
    for part in model.parts(params):
        path = runner.render(model.scad(params, part), out_dir / f"{part}.stl")
        mesh = trimesh.load(path, force="mesh")
        if not isinstance(mesh, trimesh.Trimesh):
            raise ValueError(f"parte {part} sem malha")
        meshes[part] = mesh
        files[part] = path.name

    reports = {part: mesh_report(mesh) for part, mesh in meshes.items()}
    issues = [f"{part}: {i}" for part, r in reports.items() for i in r.issues]
    issues += model.check(params, meshes)

    combined = trimesh.util.concatenate(list(meshes.values()))
    combined.export(out_dir / "completo.stl")  # type: ignore[no-untyped-call]
    x, y, z = (round(float(v), 2) for v in combined.extents)

    return GenerationResult(
        model=model.slug,
        params=params.model_dump(),
        files=files,
        combined="completo.stl",
        reports=reports,
        bbox_mm=(x, y, z),
        issues=issues,
    )
