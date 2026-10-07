"""Foto vira peça (worker) e limpeza LGPD das fotos enviadas."""

import asyncio
import inspect
import json
import logging
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any

from print3d_core.storage import LocalStorage
from print3d_mesh.photo import MODES, PhotoResult, load_image
from print3d_worker.config import get_worker_settings

PREFIX = "foto"
UPLOADS = "uploads/fotos"
log = logging.getLogger("print3d.worker")


def _export(result: PhotoResult, out: Path, mode: str) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    result.combined.export(out / "completo.stl")
    parts: list[dict[str, Any]] = []
    for name, mesh in result.parts.items():
        file = f"{name}.stl"
        mesh.export(out / file)
        parts.append(
            {"name": name, "file": file, "bbox_mm": [round(float(v), 1) for v in mesh.extents]}
        )
    report = {
        "mode": mode,
        "combined": "completo.stl",
        "bbox_mm": [round(float(v), 1) for v in result.combined.extents],
        "parts": parts,
        "info": result.info,
        "zip": "foto.zip",
    }
    (out / "relatorio.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(out / "foto.zip", "w", zipfile.ZIP_DEFLATED) as zf:
        files = ["completo.stl", *(str(p["file"]) for p in parts), "relatorio.json"]
        for file_name in files:
            zf.write(out / file_name, arcname=file_name)
    return report


async def photo_to_part(
    ctx: dict[str, Any], source_key: str, mode: str, params: dict[str, Any]
) -> dict[str, Any]:
    job_id = str(ctx.get("job_id", "manual"))
    storage = LocalStorage(Path(get_worker_settings().files_dir))
    builder = MODES[mode]
    accepted = set(inspect.signature(builder).parameters) - {"img"}
    kwargs = {k: v for k, v in params.items() if k in accepted and v is not None}
    image = load_image(storage.local_path(source_key).read_bytes())
    out = storage.local_path(f"{PREFIX}/{job_id}/relatorio.json").parent

    def work() -> dict[str, Any]:
        return _export(builder(image, **kwargs), out, mode)

    report = await asyncio.to_thread(work)
    return {**report, "prefix": f"{PREFIX}/{job_id}"}


async def purge_old_photos(ctx: dict[str, Any]) -> int:
    """LGPD: apaga fotos enviadas e resultados de foto depois do prazo configurado."""
    settings = get_worker_settings()
    root = Path(settings.files_dir)
    limit = time.time() - settings.photo_retention_days * 86400
    removed = 0
    for base in (root / UPLOADS, root / PREFIX):
        if not base.is_dir():
            continue
        for entry in base.iterdir():
            if entry.stat().st_mtime >= limit:
                continue
            if entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink(missing_ok=True)
            removed += 1
    if removed:
        log.info("fotos apagadas por prazo (LGPD)", extra={"itens": removed})
    return removed
