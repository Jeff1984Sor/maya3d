"""Peça sob medida escrita pelo assistente do painel (OpenSCAD é CPU pesado: roda no worker)."""

import asyncio
from pathlib import Path
from typing import Any

from print3d_core.storage import LocalStorage
from print3d_mesh.custom import CustomPart, generate_custom
from print3d_worker.config import get_worker_settings

PREFIX = "custom"


async def generate_custom_scad(ctx: dict[str, Any], parts: list[dict[str, str]]) -> dict[str, Any]:
    job_id = str(ctx.get("job_id", "manual"))
    storage = LocalStorage(Path(get_worker_settings().files_dir))
    out_dir = storage.local_path(f"{PREFIX}/{job_id}/completo.stl").parent
    pieces = [CustomPart(name=p["name"], scad=p["scad"]) for p in parts]
    result = await asyncio.to_thread(generate_custom, pieces, out_dir)
    return {**result, "prefix": f"{PREFIX}/{job_id}"}
