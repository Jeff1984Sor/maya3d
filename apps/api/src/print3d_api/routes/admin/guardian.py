from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.db.session import get_session
from print3d_api.models import AuditLog
from print3d_api.schemas.governance import AuditOut, GuardianCheckIn, GuardianCheckOut
from print3d_api.services import guardian

router = APIRouter(tags=["admin: guardião e auditoria"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.post("/guardian/check", response_model=GuardianCheckOut)
async def check(payload: GuardianCheckIn, session: Session) -> GuardianCheckOut:
    """Roda o Guardião sobre um produto (sem publicar) e registra a decisão na auditoria."""
    try:
        return await guardian.check(session, payload)
    except guardian.UnknownNicheError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.get("/audit", response_model=list[AuditOut])
async def list_audit(
    session: Session,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    actor: str | None = None,
    decision: str | None = None,
) -> Sequence[AuditLog]:
    """Tela de 'bloqueados' e histórico: só consulta, nunca aprovação manual."""
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if actor:
        stmt = stmt.where(AuditLog.actor == actor)
    if decision:
        stmt = stmt.where(AuditLog.decision == decision)
    return (await session.scalars(stmt)).all()
