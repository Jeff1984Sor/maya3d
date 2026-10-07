"""Marketplaces (Mercado Livre; Shopee depois): conta conectada, anúncios e perguntas.

Tokens do vendedor ficam cifrados com Fernet (TokenVault) — nunca em texto puro no banco.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from print3d_api.db.base import Base
from print3d_api.models.mixins import IdMixin, TimestampMixin


class ChannelAccount(TimestampMixin, Base):
    __tablename__ = "channel_accounts"

    channel: Mapped[str] = mapped_column(String(30), primary_key=True)  # mercadolivre | shopee
    external_user_id: Mapped[str] = mapped_column(String(40))
    nickname: Mapped[str | None] = mapped_column(String(120))
    access_token_enc: Mapped[str] = mapped_column(Text)
    refresh_token_enc: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="conectada")  # conectada | erro


class ChannelListing(IdMixin, TimestampMixin, Base):
    """Anúncio de uma variante num canal (o pedido que chega aponta a variante por aqui)."""

    __tablename__ = "channel_listings"

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(30))
    external_id: Mapped[str | None] = mapped_column(String(40), unique=True)
    category_id: Mapped[str | None] = mapped_column(String(40))
    listing_type: Mapped[str | None] = mapped_column(String(30))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # rascunho | publicado | erro | pausado
    status: Mapped[str] = mapped_column(String(20), default="rascunho")
    permalink: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    fee: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))  # tarifa real do canal


class MarketplaceQuestion(IdMixin, TimestampMixin, Base):
    """Pergunta de comprador. Responder SÓ pela plataforma (regra do marketplace)."""

    __tablename__ = "marketplace_questions"

    channel: Mapped[str] = mapped_column(String(30))
    external_id: Mapped[str] = mapped_column(String(40), unique=True)
    item_external_id: Mapped[str | None] = mapped_column(String(40))
    product_id: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pendente")  # pendente | respondida
    answer: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
