"""Geração de peças paramétricas (OpenSCAD é CPU pesado: roda no worker, nunca na API)."""

import asyncio
from pathlib import Path
from typing import Any

from print3d_core.storage import LocalStorage
from print3d_mesh.parametric import MODELS, generate
from print3d_worker.config import get_worker_settings

PREFIX = "parametric"


async def generate_parametric(
    ctx: dict[str, Any], model_slug: str, params: dict[str, Any]
) -> dict[str, Any]:
    model = MODELS[model_slug]
    job_id = str(ctx.get("job_id", "manual"))
    storage = LocalStorage(Path(get_worker_settings().files_dir))
    out_dir = storage.local_path(f"{PREFIX}/{job_id}/completo.stl").parent
    result = await asyncio.to_thread(generate, model, params, out_dir)
    data = result.model_dump(mode="json")
    data["prefix"] = f"{PREFIX}/{job_id}"
    data["printable"] = result.printable
    return data
