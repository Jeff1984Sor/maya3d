"""Biblioteca: organiza e analisa os arquivos que o dono enviou pelo painel.

Entrada: files/library/<slug>/_envios/ (ZIP, STL, 3MF, OBJ, imagens).
Saída: files/library/<slug>/modelos/<chave>/ + colecao.json (a API lê e grava no banco).
Os envios processados são apagados (os modelos ficam copiados); um novo envio soma modelos.
"""

import asyncio
import json
import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from print3d_core.storage import LocalStorage
from print3d_mesh.library import organize
from print3d_worker.config import get_worker_settings

PREFIX = "library"
log = logging.getLogger("print3d.worker")


def _run(base: Path, bed: tuple[float, float, float]) -> dict[str, Any]:
    inbox, out = base / "_envios", base / "modelos"
    if not inbox.is_dir() or not any(inbox.iterdir()):
        raise ValueError("nenhum arquivo enviado para processar")
    result = organize(inbox, out, bed)
    shutil.rmtree(inbox, ignore_errors=True)
    return result


async def process_library(ctx: dict[str, Any], slug: str, bed_mm: list[float]) -> dict[str, Any]:
    storage = LocalStorage(Path(get_worker_settings().files_dir))
    base = storage.local_path(f"{PREFIX}/{slug}/colecao.json").parent
    base.mkdir(parents=True, exist_ok=True)
    manifest = base / "colecao.json"
    started = datetime.now(UTC).isoformat()
    manifest.write_text(json.dumps({"status": "processando", "started_at": started}))
    try:
        bed = (float(bed_mm[0]), float(bed_mm[1]), float(bed_mm[2]))
        data = await asyncio.to_thread(_run, base, bed)
        payload: dict[str, Any] = {"status": "pronto", "started_at": started, **data}
    except Exception as exc:  # o painel mostra o erro
        log.exception("biblioteca: processamento falhou", extra={"slug": slug})
        payload = {"status": "erro", "started_at": started, "error": f"{exc}"[:500]}
    payload["finished_at"] = datetime.now(UTC).isoformat()
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=1))
    return {"status": payload["status"], "models": len(payload.get("models", []))}
