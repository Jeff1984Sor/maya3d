"""Painel → Mercado Livre: conectar a conta, prévia com tarifa real, anunciar e responder."""

from collections.abc import Sequence
from decimal import Decimal
from typing import Annotated, Any

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.db.session import get_session
from print3d_api.deps import get_queue
from print3d_api.models import ChannelAccount, ChannelListing, MarketplaceQuestion
from print3d_api.services import audit
from print3d_api.services import mercadolivre as ml
from print3d_channels.mercadolivre import MercadoLivreError

router = APIRouter(prefix="/mercadolivre", tags=["admin: mercado livre"])
Session = Annotated[AsyncSession, Depends(get_session)]
Redis = Annotated[ArqRedis, Depends(get_queue)]
ListingType = Annotated[str, Field(pattern=r"^(gold_special|gold_pro)$")]


class PreviewIn(BaseModel):
    variant_id: int
    price: Decimal = Field(gt=0, le=100_000)
    listing_type: ListingType = "gold_special"


class PublishIn(PreviewIn):
    attributes: dict[str, str] = Field(default_factory=dict, max_length=30)


class AnswerIn(BaseModel):
    text: str = Field(min_length=2, max_length=2000)


class ListingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    product_id: int
    variant_id: int
    external_id: str | None
    listing_type: str | None
    price: Decimal
    status: str
    permalink: str | None
    last_error: str | None
    fee: Decimal | None


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    item_external_id: str | None
    product_id: int | None
    text: str
    status: str
    answer: str | None


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, ml.MLError):
        return HTTPException(exc.status, str(exc))
    return HTTPException(502, f"Mercado Livre: {exc}")


ERRORS = (ml.MLError, MercadoLivreError)


@router.get("/status")
async def get_status(session: Session) -> dict[str, Any]:
    return await ml.status(session)


@router.post("/connect")
async def connect(session: Session, redis: Redis) -> dict[str, str]:
    """Link para o dono autorizar a loja no Mercado Livre (vale 10 minutos)."""
    try:
        return {"url": await ml.connect_url(session, redis)}
    except ERRORS as exc:
        raise _http(exc) from exc


@router.delete("/account", status_code=204)
async def disconnect(session: Session) -> None:
    account = await session.get(ChannelAccount, ml.CHANNEL)
    if account is not None:
        await session.delete(account)
        await audit.record(session, actor="admin", action="ml_desconectado")
        await session.commit()


@router.post("/preview")
async def preview(payload: PreviewIn, session: Session) -> dict[str, Any]:
    try:
        return await ml.preview(session, payload.variant_id, payload.price, payload.listing_type)
    except ERRORS as exc:
        raise _http(exc) from exc


@router.post("/listings", response_model=ListingOut)
async def publish(payload: PublishIn, session: Session) -> ChannelListing:
    try:
        return await ml.publish(
            session, payload.variant_id, payload.price, payload.listing_type, payload.attributes
        )
    except ERRORS as exc:
        raise _http(exc) from exc


@router.get("/listings", response_model=list[ListingOut])
async def listings(session: Session, product_id: int | None = None) -> Sequence[ChannelListing]:
    stmt = select(ChannelListing).where(ChannelListing.channel == ml.CHANNEL)
    if product_id:
        stmt = stmt.where(ChannelListing.product_id == product_id)
    return (await session.scalars(stmt.order_by(ChannelListing.id.desc()))).all()


@router.get("/questions", response_model=list[QuestionOut])
async def questions(session: Session) -> Sequence[MarketplaceQuestion]:
    stmt = (
        select(MarketplaceQuestion)
        .where(MarketplaceQuestion.channel == ml.CHANNEL)
        .order_by(MarketplaceQuestion.status.desc(), MarketplaceQuestion.id.desc())
        .limit(200)
    )
    return (await session.scalars(stmt)).all()


@router.post("/questions/{question_id}/answer", response_model=QuestionOut)
async def answer(question_id: int, payload: AnswerIn, session: Session) -> MarketplaceQuestion:
    try:
        return await ml.answer(session, question_id, payload.text)
    except ERRORS as exc:
        raise _http(exc) from exc
