"""Foto vira peça: guarda a foto, põe na fila (modos clássicos) ou manda para a IA de 3D.
Usado pela tela Foto vira peça e pelo assistente do painel. Foto e resultado ficam nas
pastas de fotos, que a limpeza LGPD apaga depois do prazo."""

import json
import uuid
from pathlib import Path
from typing import Any

from arq.connections import ArqRedis
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.services import audit
from print3d_core.storage import LocalStorage
from print3d_mesh.image3d import ImageTo3D

UPLOADS = "uploads/fotos"
PREFIX = "foto"
CLASSIC_MODES = ("litofania", "placa_multicor", "cortador", "chaveiro_silhueta")


class PhotoQueueError(Exception):
    pass


def _save(storage: LocalStorage, data: bytes, ext: str) -> tuple[str, str]:
    ref = uuid.uuid4().hex
    key = f"{UPLOADS}/{ref}.{ext}"
    path = storage.local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return ref, key


def task_folder(storage: LocalStorage, ref: str) -> Path:
    return storage.local_path(f"{PREFIX}/ia-{ref}/tarefa.json").parent


def save_task(folder: Path, state: dict[str, Any]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "tarefa.json").write_text(json.dumps(state, ensure_ascii=False))


async def enqueue_part(
    session: AsyncSession,
    storage: LocalStorage,
    queue: ArqRedis,
    *,
    data: bytes,
    ext: str,
    mode: str,
    params: dict[str, Any],
    reason: str,
) -> str:
    """Modos clássicos (litofania etc.): roda no worker. Devolve o id do job."""
    _, key = _save(storage, data, ext)
    job = await queue.enqueue_job("photo_to_part", key, mode, params)
    if job is None:
        raise PhotoQueueError("job duplicado")
    await audit.record(
        session,
        actor="admin",
        action="foto_enviada",
        entity_type="foto",
        entity_id=job.job_id,
        reason=reason,
        payload={"modo": mode, "arquivo": key},
    )
    await session.commit()
    return job.job_id


async def start_3d(
    session: AsyncSession,
    storage: LocalStorage,
    provider: ImageTo3D,
    *,
    data: bytes,
    mime: str,
    ext: str,
    size_mm: float,
    reason: str,
) -> str:
    """Objeto 3D por IA: manda para o serviço e guarda a tarefa. Devolve o id da tarefa."""
    task_id = await provider.submit(data, mime)
    ref, key = _save(storage, data, ext)
    save_task(task_folder(storage, ref), {"task_id": task_id, "size_mm": size_mm, "status": "fila"})
    await audit.record(
        session,
        actor="admin",
        action="foto_enviada",
        entity_type="foto",
        entity_id=ref,
        reason=reason,
        payload={"modo": "objeto_3d", "arquivo": key, "tarefa": task_id},
    )
    await session.commit()
    return ref
