from collections.abc import Sequence
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.db.session import get_session
from print3d_api.models import Notification, OpsConfig
from print3d_api.models.orders import OPS_CONFIG_ID
from print3d_api.schemas.orders import (
    AdvanceIn,
    NotificationOut,
    OpsConfigIn,
    OpsConfigOut,
    OrderCreate,
    OrderDetail,
    OrderSummary,
    PrintJobOut,
    QueueGroup,
)
from print3d_api.services import audit, orders

router = APIRouter(tags=["admin: pedidos e produção"])
Session = Annotated[AsyncSession, Depends(get_session)]


def _http(exc: orders.OrderError) -> HTTPException:
    code = status.HTTP_404_NOT_FOUND if exc.not_found else status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(code, str(exc))


@router.get("/orders", response_model=list[OrderSummary])
async def list_orders(
    session: Session, status_: Annotated[str | None, Query(alias="status")] = None
) -> list[OrderSummary]:
    return await orders.list_orders(session, status_)


@router.post("/orders", response_model=OrderDetail, status_code=status.HTTP_201_CREATED)
async def create_order(payload: OrderCreate, session: Session) -> OrderDetail:
    """Registra uma venda (canal manual/B2B ou simulação). Marketplaces entram via integração."""
    try:
        order = await orders.create_order(session, payload)
    except orders.OrderError as exc:
        await session.rollback()
        raise _http(exc) from exc
    return await orders.detail(session, order.id)


@router.get("/orders/{order_id}", response_model=OrderDetail)
async def get_order(order_id: int, session: Session) -> OrderDetail:
    try:
        return await orders.detail(session, order_id)
    except orders.OrderError as exc:
        raise _http(exc) from exc


@router.post("/orders/{order_id}/advance", response_model=OrderDetail)
async def advance(order_id: int, payload: AdvanceIn, session: Session) -> OrderDetail:
    """Botão da tela Produção: avança o status, grava a linha do tempo e avisa o cliente."""
    try:
        await orders.advance(
            session,
            order_id,
            payload.to,
            note=payload.note,
            media_url=payload.media_url,
            actor="admin",
        )
    except orders.OrderError as exc:
        await session.rollback()
        raise _http(exc) from exc
    return await orders.detail(session, order_id)


class JobActionIn(BaseModel):
    action: Literal["iniciar", "concluir", "falhou"]
    reason: str | None = None
    printer_id: int | None = None


@router.get("/print-queue", response_model=list[QueueGroup])
async def print_queue(session: Session) -> list[QueueGroup]:
    return await orders.print_queue(session)


@router.post("/print-jobs/{job_id}", response_model=PrintJobOut)
async def job_action(job_id: int, payload: JobActionIn, session: Session) -> PrintJobOut:
    try:
        job = await orders.job_action(
            session, job_id, payload.action, reason=payload.reason, printer_id=payload.printer_id
        )
    except orders.OrderError as exc:
        await session.rollback()
        raise _http(exc) from exc
    return PrintJobOut.model_validate(job)


@router.get("/ops-config", response_model=OpsConfigOut)
async def get_ops(session: Session) -> OpsConfig:
    ops = await session.get(OpsConfig, OPS_CONFIG_ID)
    if ops is None:
        raise HTTPException(503, "ops_config ausente")
    return ops


@router.put("/ops-config", response_model=OpsConfigOut)
async def put_ops(payload: OpsConfigIn, session: Session) -> OpsConfig:
    ops = await session.get(OpsConfig, OPS_CONFIG_ID)
    if ops is None:
        raise HTTPException(503, "ops_config ausente")
    for field, value in payload.model_dump().items():
        setattr(ops, field, value)
    await audit.record(
        session,
        actor="admin",
        action="operacao_alterada",
        entity_type="ops_config",
        entity_id=OPS_CONFIG_ID,
        payload=payload.model_dump(mode="json"),
    )
    await session.commit()
    await session.refresh(ops)
    return ops


@router.get("/notifications", response_model=list[NotificationOut])
async def list_notifications(
    session: Session,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    status_: Annotated[str | None, Query(alias="status")] = None,
) -> Sequence[Notification]:
    """Caixa de saída: o que foi (ou será, quando o WhatsApp estiver conectado) enviado."""
    stmt = select(Notification).order_by(Notification.id.desc()).limit(limit)
    if status_:
        stmt = stmt.where(Notification.status == status_)
    return (await session.scalars(stmt)).all()
