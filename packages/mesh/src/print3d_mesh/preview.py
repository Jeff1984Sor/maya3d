"""Prévia 3D leve para a loja: malha simplificada e escalada, só para visualizar.

Não serve para imprimir (poucos triângulos), o que também protege o arquivo original.
"""

from pathlib import Path

import trimesh

PREVIEW_FACES = 25_000


def make_preview(source: Path, out: Path, *, height_mm: float | None = None) -> Path:
    mesh = trimesh.load(source, force="mesh")
    if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
        raise ValueError("arquivo sem malha")
    if len(mesh.faces) > PREVIEW_FACES:
        mesh = mesh.simplify_quadric_decimation(face_count=PREVIEW_FACES)
    if height_mm:
        mesh.apply_scale(height_mm / float(max(mesh.extents)))  # type: ignore[no-untyped-call]
    out.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(out)
    return out
