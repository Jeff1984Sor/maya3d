"""Foto vira peça pelo painel. O dono declarou ter direito sobre as fotos que envia
(registrado na auditoria); na loja, o cliente confirma a cada envio (spec 3 e LGPD)."""

import uuid
from typing import Annotated, Literal

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.config import Settings
from print3d_api.db.session import get_session
from print3d_api.deps import get_app_settings, get_queue, get_storage
from print3d_api.services import audit
from print3d_core.storage import LocalStorage

router = APIRouter(prefix="/photo", tags=["admin: foto vira peça"])
IMAGE_TYPES = frozenset({"jpg", "jpeg", "png", "webp"})
Mode = Literal["litofania", "placa_multicor", "cortador", "chaveiro_silhueta"]


class PhotoJob(BaseModel):
    job_id: str


@router.post("/{mode}", response_model=PhotoJob, status_code=202)
async def photo_to_part(
    mode: Mode,
    file: UploadFile,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    storage: Annotated[LocalStorage, Depends(get_storage)],
    queue: Annotated[ArqRedis, Depends(get_queue)],
    width_mm: Annotated[float | None, Form(ge=20, le=300)] = None,
    size_mm: Annotated[float | None, Form(ge=15, le=250)] = None,
    min_mm: Annotated[float | None, Form(ge=0.4, le=5)] = None,
    max_mm: Annotated[float | None, Form(ge=0.8, le=8)] = None,
    frame_mm: Annotated[float | None, Form(ge=0, le=15)] = None,
    colors: Annotated[int | None, Form(ge=2, le=4)] = None,
    thickness_mm: Annotated[float | None, Form(ge=2, le=10)] = None,
    height_mm: Annotated[float | None, Form(ge=6, le=40)] = None,
    invert: Annotated[bool, Form()] = False,
) -> PhotoJob:
    name = file.filename or "foto"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in IMAGE_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "use JPG, PNG ou WEBP")
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"máximo {settings.max_upload_mb} MB"
        )
    key = f"uploads/fotos/{uuid.uuid4().hex}.{ext}"
    path = storage.local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    params = {
        "width_mm": width_mm,
        "size_mm": size_mm,
        "min_mm": min_mm,
        "max_mm": max_mm,
        "frame_mm": frame_mm,
        "colors": colors,
        "thickness_mm": thickness_mm,
        "height_mm": height_mm,
        "invert": invert,
    }
    job = await queue.enqueue_job("photo_to_part", key, mode, params)
    if job is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "job duplicado")
    await audit.record(
        session,
        actor="admin",
        action="foto_enviada",
        entity_type="foto",
        entity_id=job.job_id,
        reason="direito de uso declarado pelo dono; apagada após o prazo LGPD",
        payload={"modo": mode, "arquivo": key},
    )
    await session.commit()
    return PhotoJob(job_id=job.job_id)
