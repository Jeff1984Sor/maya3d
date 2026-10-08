from pathlib import Path

import trimesh

from print3d_mesh.preview import PREVIEW_FACES, make_preview


def test_previa_leve_e_escalada(tmp_path: Path) -> None:
    src = tmp_path / "a.stl"
    trimesh.creation.icosphere(subdivisions=6, radius=0.5).export(src)  # ~80 mil faces, 1 mm
    out = make_preview(src, tmp_path / "p.stl", height_mm=150)
    mesh = trimesh.load(out, force="mesh")
    assert len(mesh.faces) <= PREVIEW_FACES
    assert abs(max(mesh.extents) - 150) < 1
