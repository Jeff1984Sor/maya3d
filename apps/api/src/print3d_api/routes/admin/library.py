"""Biblioteca de modelos: o dono cria uma coleção, envia ZIP/STL/3MF pelo painel, o worker
organiza e analisa, e cada modelo vira produto com um clique."""

import shutil
from typing import Annotated, Any

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.config import Settings
from print3d_api.db.session import get_session
from print3d_api.deps import get_app_settings, get_queue, get_storage
from print3d_api.models import LibraryModel, Niche
from print3d_api.services import library
from print3d_core.storage import LocalStorage

router = APIRouter(prefix="/library", tags=["admin: biblioteca"])
Session = Annotated[AsyncSession, Depends(get_session)]
Storage = Annotated[LocalStorage, Depends(get_storage)]
CHUNK = 1024 * 1024


class CollectionIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    niche: str
    category: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    license_text: str | None = Field(default=None, max_length=300)


class LicenseIn(BaseModel):
    license_text: str | None = Field(default=None, max_length=300)


class ProductFromModel(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    key: str
    title: str
    files: list[dict[str, Any]]
    cover: str | None
    bbox_mm: list[float] | None
    fits: bool | None
    issues: list[str]
    status: str
    product_id: int | None


def _http(exc: library.LibraryError) -> HTTPException:
    code = status.HTTP_404_NOT_FOUND if exc.not_found else status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(code, str(exc))


@router.get("/collections")
async def list_collections(session: Session, storage: Storage) -> list[dict[str, Any]]:
    return await library.list_collections(session, storage)


@router.post("/collections", status_code=201)
async def create_collection(payload: CollectionIn, session: Session) -> dict[str, str]:
    if await session.scalar(select(Niche).where(Niche.slug == payload.niche)) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "nicho não existe")
    col = await library.create_collection(session, payload.model_dump())
    return {"slug": col.slug}


@router.post("/collections/{slug}/files")
async def upload_file(
    slug: str,
    file: UploadFile,
    session: Session,
    storage: Storage,
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> dict[str, Any]:
    """Um arquivo por chamada (o painel envia um a um, com progresso)."""
    try:
        await library.get_collection(session, slug)
        name = library.safe_upload_name(file.filename or "")
    except library.LibraryError as exc:
        raise _http(exc) from exc
    inbox = library.inbox_dir(storage, slug)
    inbox.mkdir(parents=True, exist_ok=True)
    dest = inbox / name
    stem, n = dest.stem, 2
    while dest.exists():
        dest, n = inbox / f"{stem}-{n}{dest.suffix}", n + 1
    limit = settings.library_upload_mb * 1024 * 1024
    written = 0
    with dest.open("wb") as out:
        while chunk := await file.read(CHUNK):
            written += len(chunk)
            if written > limit:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    f"máximo {settings.library_upload_mb} MB por arquivo",
                )
            out.write(chunk)
    return {"name": dest.name, "bytes": written}


@router.delete("/collections/{slug}/files", status_code=204)
async def clear_pending(slug: str, session: Session, storage: Storage) -> None:
    """Descarta envios ainda não processados (não mexe nos modelos já organizados)."""
    try:
        await library.get_collection(session, slug)
    except library.LibraryError as exc:
        raise _http(exc) from exc
    shutil.rmtree(library.inbox_dir(storage, slug), ignore_errors=True)


@router.post("/collections/{slug}/process", status_code=202)
async def process(
    slug: str,
    session: Session,
    storage: Storage,
    queue: Annotated[ArqRedis, Depends(get_queue)],
) -> dict[str, Any]:
    try:
        col = await library.get_collection(session, slug)
    except library.LibraryError as exc:
        raise _http(exc) from exc
    inbox = library.inbox_dir(storage, slug)
    if not inbox.is_dir() or not any(inbox.iterdir()):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "envie arquivos antes")
    if col.status == "processando":
        raise HTTPException(status.HTTP_409_CONFLICT, "já está processando")
    job = await queue.enqueue_job(
        "process_library", slug, await library.bed_mm(session), _job_id=f"biblioteca-{slug}"
    )
    library.mark_processing(col)
    await session.commit()
    return {"job_id": job.job_id if job else None}


@router.post("/collections/{slug}/sync")
async def sync(slug: str, session: Session, storage: Storage) -> dict[str, str]:
    try:
        col = await library.get_collection(session, slug)
    except library.LibraryError as exc:
        raise _http(exc) from exc
    await library.sync(session, storage, col)
    return {"status": col.status}


@router.put("/collections/{slug}/license")
async def put_license(slug: str, payload: LicenseIn, session: Session) -> dict[str, int]:
    try:
        count = await library.set_license(session, slug, payload.license_text or None)
    except library.LibraryError as exc:
        raise _http(exc) from exc
    return {"rechecked": count}


@router.get("/collections/{slug}/models", response_model=list[ModelOut])
async def list_models(slug: str, session: Session, storage: Storage) -> list[Any]:
    try:
        col = await library.get_collection(session, slug)
    except library.LibraryError as exc:
        raise _http(exc) from exc
    await library.sync(session, storage, col)
    return await library.models_of(session, slug)


@router.post("/models/{model_id}/product")
async def product_from_model(
    model_id: int, payload: ProductFromModel, session: Session
) -> dict[str, Any]:
    try:
        model, product = await library.create_product(session, model_id, payload.title)
    except library.LibraryError as exc:
        raise _http(exc) from exc
    return {
        "product_id": product.id,
        "guardian": product.guardian_status,
        "reason": product.guardian_reason,
        "model": model.id,
    }


@router.post("/models/{model_id}/ignore")
async def ignore_model(model_id: int, session: Session) -> dict[str, str]:
    model = await session.get(LibraryModel, model_id)
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "modelo não existe")
    if model.status != "produto":
        model.status = "novo" if model.status == "ignorado" else "ignorado"
    await session.commit()
    return {"status": model.status}
