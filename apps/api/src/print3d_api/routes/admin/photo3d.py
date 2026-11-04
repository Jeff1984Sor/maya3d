"""Foto vira objeto 3D por IA (Meshy). A chave fica no painel; quem fala com o serviço é a
API (o worker não vê a chave). O painel consulta o andamento; quando a IA termina, a API baixa
o modelo, conserta, põe no tamanho pedido e grava STL + 3MF. O dono declarou ter direito sobre
a foto (auditoria); a foto e o resultado seguem o prazo LGPD das fotos."""

import json
import uuid
from pathlib import Path
from typing import Annotated, Any

import trimesh
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from print3d_api.config import Settings
from print3d_api.db.session import get_session
from print3d_api.deps import get_app_settings, get_storage
from print3d_api.services import audit, integrations
from print3d_core.storage import LocalStorage
from print3d_mesh.image3d import Image3DError, ImageTo3D, prepare_for_print

router = APIRouter(prefix="/photo3d", tags=["admin: foto vira objeto 3D"])
IMAGE_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
PREFIX = "foto"  # mesma pasta das fotos: a limpeza LGPD já cobre


class Photo3DState(BaseModel):
    id: str
    status: str  # fila | processando | concluido | falhou
    progress: int = 0
    error: str | None = None
    result: dict[str, Any] | None = None


async def get_image_to_3d(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ImageTo3D:
    provider = await integrations.image_to_3d(session)
    if provider is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "cole a chave da Meshy em Integrações → Foto vira objeto 3D",
        )
    return provider


Provider = Annotated[ImageTo3D, Depends(get_image_to_3d)]
Storage = Annotated[LocalStorage, Depends(get_storage)]


def _folder(storage: LocalStorage, ref: str) -> Path:
    return storage.local_path(f"{PREFIX}/ia-{ref}/tarefa.json").parent


def _save(folder: Path, state: dict[str, Any]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "tarefa.json").write_text(json.dumps(state, ensure_ascii=False))


def _error_status(exc: Image3DError) -> int:
    return exc.status_code if exc.status_code in (402, 403, 429) else status.HTTP_502_BAD_GATEWAY


@router.post("", response_model=Photo3DState, status_code=202)
async def start(
    file: UploadFile,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    storage: Storage,
    provider: Provider,
    size_mm: Annotated[float, Form(ge=20, le=3000)] = 150.0,
) -> Photo3DState:
    """Manda a foto para a IA de 3D. O tamanho é o do maior lado da peça final."""
    name = file.filename or "foto"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in IMAGE_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "use JPG, PNG ou WEBP")
    limit = min(settings.max_upload_mb, 20) * 1024 * 1024  # a Meshy aceita até 20 MB
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "foto grande demais")
    try:
        task_id = await provider.submit(data, IMAGE_TYPES[ext])
    except Image3DError as exc:
        raise HTTPException(_error_status(exc), str(exc)) from exc

    ref = uuid.uuid4().hex
    key = f"uploads/fotos/{ref}.{ext}"
    path = storage.local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    _save(_folder(storage, ref), {"task_id": task_id, "size_mm": size_mm, "status": "fila"})
    await audit.record(
        session,
        actor="admin",
        action="foto_enviada",
        entity_type="foto",
        entity_id=ref,
        reason="foto → objeto 3D (IA); direito de uso declarado pelo dono; prazo LGPD",
        payload={"modo": "objeto_3d", "arquivo": key, "tarefa": task_id},
    )
    await session.commit()
    return Photo3DState(id=ref, status="fila")


def _finish(folder: Path, model: bytes, size_mm: float) -> dict[str, Any]:
    printable = prepare_for_print(model, "stl", size_mm)
    printable.mesh.export(folder / "modelo.stl")
    scene = trimesh.Scene()
    scene.add_geometry(printable.mesh, node_name="modelo", geom_name="modelo")
    scene.export(folder / "modelo.3mf")  # type: ignore[no-untyped-call]
    return {**printable.info, "model": "modelo.stl", "project": "modelo.3mf"}


@router.get("/{ref}", response_model=Photo3DState)
async def state(ref: str, storage: Storage, provider: Provider) -> Photo3DState:
    if not ref.isalnum() or len(ref) != 32:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "id inválido")
    folder = _folder(storage, ref)
    try:
        saved = json.loads((folder / "tarefa.json").read_text())
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "tarefa não existe (ou já expirou)") from exc
    if saved["status"] in ("concluido", "falhou"):
        return Photo3DState(id=ref, **{k: saved.get(k) for k in ("status", "error", "result")})
    try:
        task = await provider.task(saved["task_id"])
        if task.status == "falhou":
            saved |= {"status": "falhou", "error": task.error or "a IA não conseguiu gerar"}
        elif task.status == "concluido" and task.model_url:
            model = await provider.download(task.model_url)
            result = await run_in_threadpool(_finish, folder, model, float(saved["size_mm"]))
            result |= {"prefix": f"{PREFIX}/ia-{ref}", "credits": task.credits}
            saved |= {"status": "concluido", "result": result}
        else:
            return Photo3DState(id=ref, status=task.status, progress=task.progress)
    except Image3DError as exc:
        if exc.status_code in (401, 403):  # chave/plano: não adianta seguir consultando
            saved |= {"status": "falhou", "error": str(exc)}
        else:
            raise HTTPException(_error_status(exc), str(exc)) from exc
    _save(folder, saved)
    return Photo3DState(
        id=ref,
        status=saved["status"],
        progress=100,
        error=saved.get("error"),
        result=saved.get("result"),
    )
