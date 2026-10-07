"""Modelos paramétricos: catálogo de modelos, geração (via worker), status e arquivos."""

from typing import Annotated, Any, Literal

from arq.connections import ArqRedis
from arq.jobs import Job, JobStatus
from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.db.session import get_session
from print3d_api.deps import get_queue, get_storage
from print3d_api.schemas.governance import GuardianCheckIn
from print3d_api.services import guardian
from print3d_core.storage import LocalStorage, StorageError
from print3d_mesh.parametric import MODELS

router = APIRouter(tags=["admin: paramétricos"])
Session = Annotated[AsyncSession, Depends(get_session)]
Queue = Annotated[ArqRedis, Depends(get_queue)]

# Parâmetros de texto livre que o cliente digita: passam pelo Guardião (palavrão, marca, time...).
TEXT_PARAMS = ("letter", "name", "lid_text")


class ModelInfo(BaseModel):
    slug: str
    title: str
    niche: str
    description: str
    params_schema: dict[str, Any]


class JobCreated(BaseModel):
    job_id: str


class JobState(BaseModel):
    job_id: str
    status: Literal["fila", "processando", "concluido", "falhou", "desconhecido"]
    result: dict[str, Any] | None = None
    error: str | None = None


@router.get("/parametric", response_model=list[ModelInfo])
async def list_models() -> list[ModelInfo]:
    return [
        ModelInfo(
            slug=m.slug,
            title=m.title,
            niche=m.niche,
            description=m.description,
            params_schema=m.params_model.model_json_schema(),
        )
        for m in MODELS.values()
    ]


@router.post("/parametric/{slug}/generate", response_model=JobCreated, status_code=202)
async def generate(
    slug: str,
    params: Annotated[dict[str, Any], Body()],
    session: Session,
    queue: Queue,
) -> JobCreated:
    model = MODELS.get(slug)
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"modelo '{slug}' não existe")
    try:
        parsed = model.parse(params)
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, exc.errors(include_url=False)
        ) from exc

    texts = [str(v) for k in TEXT_PARAMS if (v := getattr(parsed, k, None))]
    if texts:
        verdict = await guardian.check(
            session,
            GuardianCheckIn(
                niche=model.niche, title=model.title, origin="parametrico", customer_text=texts
            ),
        )
        if not verdict.approved:
            reasons = "; ".join(v.message for v in verdict.violations)
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"texto recusado: {reasons}")

    job = await queue.enqueue_job("generate_parametric", slug, parsed.model_dump())
    if job is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "job duplicado")
    return JobCreated(job_id=job.job_id)


_STATUS = {
    JobStatus.deferred: "fila",
    JobStatus.queued: "fila",
    JobStatus.in_progress: "processando",
    JobStatus.complete: "concluido",
    JobStatus.not_found: "desconhecido",
}


@router.get("/jobs/{job_id}", response_model=JobState)
async def job_state(job_id: str, queue: Queue) -> JobState:
    job = Job(job_id, redis=queue)
    state = await job.status()
    if state != JobStatus.complete:
        return JobState(job_id=job_id, status=_STATUS.get(state, "desconhecido"))
    info = await job.result_info()
    if info is None or not info.success:
        detail = str(info.result) if info is not None else "sem resultado"
        return JobState(job_id=job_id, status="falhou", error=detail[:500])
    return JobState(job_id=job_id, status="concluido", result=info.result)


@router.get("/files/{key:path}")
async def download(
    key: str, storage: Annotated[LocalStorage, Depends(get_storage)]
) -> FileResponse:
    try:
        path = storage.local_path(key)
    except StorageError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "arquivo não existe")
    media = "model/stl" if path.suffix == ".stl" else "application/octet-stream"
    return FileResponse(path, media_type=media, filename=path.name)
