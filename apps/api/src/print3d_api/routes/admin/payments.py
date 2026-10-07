"""Painel → pagamentos (Mercado Pago)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.db.session import get_session
from print3d_api.services import payments
from print3d_channels.mercadopago import MercadoPagoError

router = APIRouter(prefix="/payments", tags=["admin: pagamentos"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/status")
async def get_status(session: Session) -> dict[str, Any]:
    return await payments.status(session)


@router.post("/check")
async def check_now(session: Session) -> dict[str, int]:
    """Confere agora os Pix pendentes (o sistema já faz isso sozinho a cada 2 minutos)."""
    try:
        return {"approved": await payments.poll_pending(session)}
    except MercadoPagoError as exc:
        raise HTTPException(502, str(exc)) from exc
