import uuid
from typing import Annotated

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from print3d_api.config import Settings
from print3d_api.db.session import get_session
from print3d_api.deps import get_app_settings, get_queue, get_storage
from print3d_api.models import Printer
from print3d_core.storage import LocalStorage
from print3d_mesh import (
    SUPPORTED_TYPES,
    MeshAnalysisError,
    MeshReport,
    TrimeshAnalyzer,
    fits_build_volume,
)

router = APIRouter(prefix="/mesh", tags=["admin: 3D"])
_analyzer = TrimeshAnalyzer()


class PrinterFit(BaseModel):
    printer_id: int
    name: str
    fits: bool


class MeshAnalysisOut(BaseModel):
    filename: str
    report: MeshReport
    printers: list[PrinterFit]


@router.post("/analyze", response_model=MeshAnalysisOut)
async def analyze(
    file: UploadFile,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> MeshAnalysisOut:
    """Medidas, volume, malha fechada e em quais impressoras cadastradas a peça cabe."""
    name = file.filename or "arquivo"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in SUPPORTED_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"use {', '.join(sorted(SUPPORTED_TYPES))}"
        )
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"máximo {settings.max_upload_mb} MB"
        )

    try:
        report = await run_in_threadpool(_analyzer.analyze_bytes, data, ext)
    except MeshAnalysisError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    printers = (await session.scalars(select(Printer).where(Printer.status != "inativa"))).all()
    return MeshAnalysisOut(
        filename=name,
        report=report,
        printers=[
            PrinterFit(
                printer_id=p.id,
                name=p.name,
                fits=fits_build_volume(report.bbox_mm, (p.bed_x_mm, p.bed_y_mm, p.bed_z_mm)),
            )
            for p in printers
        ],
    )


class SplitJob(BaseModel):
    job_id: str
    bed_mm: tuple[float, float, float]


@router.post("/split", response_model=SplitJob, status_code=202)
async def split(
    file: UploadFile,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    storage: Annotated[LocalStorage, Depends(get_storage)],
    queue: Annotated[ArqRedis, Depends(get_queue)],
    printer_id: Annotated[int, Form()],
    pin_diameter_mm: Annotated[float, Form(ge=2, le=10)] = 4.0,
    clearance_mm: Annotated[float, Form(ge=0.05, le=0.8)] = 0.25,
    margin_mm: Annotated[float, Form(ge=0, le=20)] = 3.0,
) -> SplitJob:
    """Peça grande → pedaços que cabem na impressora escolhida, com furos e pinos de encaixe."""
    printer = await session.get(Printer, printer_id)
    if printer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "impressora não existe")
    name = file.filename or "arquivo"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in SUPPORTED_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"use {', '.join(sorted(SUPPORTED_TYPES))}"
        )
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, f"máximo {settings.max_upload_mb} MB"
        )
    key = f"uploads/{uuid.uuid4().hex}.{ext}"
    path = storage.local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

    bed = (float(printer.bed_x_mm), float(printer.bed_y_mm), float(printer.bed_z_mm))
    job = await queue.enqueue_job(
        "split_model",
        key,
        {
            "bed_mm": list(bed),
            "pin_diameter_mm": pin_diameter_mm,
            "clearance_mm": clearance_mm,
            "margin_mm": margin_mm,
        },
    )
    if job is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "job duplicado")
    return SplitJob(job_id=job.job_id, bed_mm=bed)
