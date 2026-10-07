"""Letras de montagem (A, B, C...) geradas pelo OpenSCAD com a fonte OFL do projeto.

Cada letra vira um sólido de z=0 a z=profundidade, centrado na origem; o `split_mesh` a
posiciona e grava nas duas faces de cada junção.
"""

import tempfile
from functools import lru_cache
from pathlib import Path

import trimesh

from print3d_mesh.parametric.fonts import FONTS, scad_font_uses
from print3d_mesh.parametric.openscad import OpenScadRunner, scad_string
from print3d_mesh.split import TextFactory


def openscad_text_factory(
    runner: OpenScadRunner, *, size_mm: float, depth_mm: float
) -> TextFactory | None:
    """Fábrica de letras; None se não houver OpenSCAD (as peças saem sem etiqueta)."""
    if not runner.available():
        return None
    font = FONTS["bold"].scad_name

    @lru_cache(maxsize=128)
    def make(label: str) -> trimesh.Trimesh:
        source = "\n".join(
            [
                scad_font_uses(),
                f"linear_extrude({depth_mm}) text({scad_string(label)}, size={size_mm}, "
                f'font={scad_string(font)}, halign="center", valign="center");',
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = runner.render(source, Path(tmp) / "letra.stl")
            mesh = trimesh.load(path, force="mesh")
        if not isinstance(mesh, trimesh.Trimesh):
            raise ValueError(f"letra {label} sem malha")
        return mesh

    def factory(label: str) -> trimesh.Trimesh:
        return make(label).copy()

    return factory
