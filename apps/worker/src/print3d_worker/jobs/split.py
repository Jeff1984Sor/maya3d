"""Divisão de peça grande em pedaços com pinos (booleanas pesadas: roda no worker)."""

import asyncio
import json
import zipfile
from pathlib import Path
from typing import Any

import trimesh

from print3d_core.storage import LocalStorage
from print3d_mesh.parametric import OpenScadRunner
from print3d_mesh.split import SplitOptions, SplitResult, split_mesh
from print3d_mesh.split_labels import openscad_text_factory
from print3d_worker.config import get_worker_settings

PREFIX = "split"
EXPLODE_GAP_MM = 15.0


def _export(result: SplitResult, out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    pieces: list[dict[str, Any]] = []
    exploded: list[trimesh.Trimesh] = []
    for piece in result.pieces:
        file = f"{piece.name}.stl"
        piece.mesh.export(out / file)
        offset = [i * EXPLODE_GAP_MM for i in piece.index]
        exploded.append(piece.mesh.copy().apply_translation(offset))
        pieces.append(
            {
                "name": piece.name,
                "file": file,
                "bbox_mm": [round(float(v), 1) for v in piece.mesh.extents],
                "volume_cm3": round(float(piece.mesh.volume) / 1000, 1),
                "fits": piece.fits,
            }
        )
    files = [p["file"] for p in pieces]
    if result.pins:
        trimesh.util.concatenate(result.pins).export(out / "pinos.stl")  # type: ignore[no-untyped-call]
        files.append("pinos.stl")
    trimesh.util.concatenate(exploded).export(out / "explodido.stl")  # type: ignore[no-untyped-call]

    report = {
        "plan": {"counts": list(result.plan.counts), "cell_mm": list(result.plan.cell_mm)},
        "pieces": pieces,
        "pins": {"count": len(result.pins), "file": "pinos.stl" if result.pins else None},
        "faces_without_pins": result.faces_without_pins,
        "cuts": {str(axis): coords for axis, coords in result.cuts.items()},
        "seam_area_cm2": round(result.seam_area_mm2 / 100, 1),
        "labels": result.labels,
        "warnings": result.warnings,
        "exploded": "explodido.stl",
        "zip": "pecas.zip",
    }
    (out / "relatorio.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(out / "pecas.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        for name in [*files, "relatorio.json"]:
            zf.write(out / name, arcname=name)
    return report


async def split_model(
    ctx: dict[str, Any], source_key: str, options: dict[str, Any]
) -> dict[str, Any]:
    job_id = str(ctx.get("job_id", "manual"))
    storage = LocalStorage(Path(get_worker_settings().files_dir))
    mesh = trimesh.load(storage.local_path(source_key), force="mesh")
    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError("arquivo sem malha")
    opts = SplitOptions(**{**options, "bed_mm": tuple(options["bed_mm"])})
    out = storage.local_path(f"{PREFIX}/{job_id}/relatorio.json").parent

    factory = openscad_text_factory(
        OpenScadRunner(), size_mm=opts.label_size_mm, depth_mm=opts.label_depth_mm
    )

    def work() -> dict[str, Any]:
        return _export(split_mesh(mesh, opts, factory), out)

    report = await asyncio.to_thread(work)
    return {**report, "prefix": f"{PREFIX}/{job_id}"}
