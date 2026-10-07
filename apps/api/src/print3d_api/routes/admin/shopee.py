"""Painel → Shopee: conectar a loja, anunciar variantes e ver anúncios."""

from collections.abc import Sequence
from decimal import Decimal
from typing import Annotated, Any

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.db.session import get_session
from print3d_api.deps import get_queue, get_storage
from print3d_api.models import ChannelAccount, ChannelListing
from print3d_api.routes.admin.mercadolivre import ListingOut
from print3d_api.services import audit
from print3d_api.services import shopee as sp
from print3d_channels.shopee import ShopeeError
from print3d_core.storage import LocalStorage

router = APIRouter(prefix="/shopee", tags=["admin: shopee"])
Session = Annotated[AsyncSession, Depends(get_session)]


class PublishIn(BaseModel):
    variant_id: int
    price: Decimal = Field(gt=0, le=100_000)


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, sp.ShopeeServiceError):
        return HTTPException(exc.status, str(exc))
    return HTTPException(502, f"Shopee: {exc}")


@router.get("/status")
async def get_status(session: Session) -> dict[str, Any]:
    return await sp.status(session)


@router.post("/connect")
async def connect(
    session: Session, redis: Annotated[ArqRedis, Depends(get_queue)]
) -> dict[str, str]:
    try:
        return {"url": await sp.connect_url(session, redis)}
    except (sp.ShopeeServiceError, ShopeeError) as exc:
        raise _http(exc) from exc


@router.delete("/account", status_code=204)
async def disconnect(session: Session) -> None:
    account = await session.get(ChannelAccount, sp.CHANNEL)
    if account is not None:
        await session.delete(account)
        await audit.record(session, actor="admin", action="shopee_desconectada")
        await session.commit()


@router.post("/listings", response_model=ListingOut)
async def publish(
    payload: PublishIn, session: Session, storage: Annotated[LocalStorage, Depends(get_storage)]
) -> ChannelListing:
    try:
        return await sp.publish(session, storage, payload.variant_id, payload.price)
    except (sp.ShopeeServiceError, ShopeeError) as exc:
        raise _http(exc) from exc


@router.get("/listings", response_model=list[ListingOut])
async def listings(session: Session, product_id: int | None = None) -> Sequence[ChannelListing]:
    stmt = select(ChannelListing).where(ChannelListing.channel == sp.CHANNEL)
    if product_id:
        stmt = stmt.where(ChannelListing.product_id == product_id)
    return (await session.scalars(stmt.order_by(ChannelListing.id.desc()))).all()
