"""Configuração de custos (singleton) e tarifas por canal (spec seção 2 — Precificação)."""

from decimal import Decimal

from sqlalchemy import CheckConstraint, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from print3d_api.db.base import Base
from print3d_api.models.mixins import IdMixin, TimestampMixin

COST_CONFIG_ID = 1


class CostConfig(TimestampMixin, Base):
    __tablename__ = "cost_config"
    __table_args__ = (CheckConstraint(f"id = {COST_CONFIG_ID}", name="singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=COST_CONFIG_ID)
    energy_price_kwh: Mapped[Decimal] = mapped_column(Numeric(8, 4))
    labor_per_hour: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    failure_rate: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    min_profit: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    default_margin: Mapped[Decimal] = mapped_column(Numeric(5, 4))
    # {"religioso/nossa-senhora": "0.45", ...} — margem por categoria sobrescreve a padrão
    margin_by_category: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict)


class ChannelFeeBand(IdMixin, TimestampMixin, Base):
    """Faixa de tarifa de um canal. Preenchida via API do canal (Fases 3/4) ou manualmente.

    channel: mercadolivre_classico | mercadolivre_premium | shopee | site_pix | site_card ...
    category: categoria interna; NULL = vale para todas as categorias sem faixa própria.
    """

    __tablename__ = "channel_fee_bands"

    channel: Mapped[str] = mapped_column(String(40), index=True)
    category: Mapped[str | None] = mapped_column(String(120))
    min_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal(0))
    max_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    commission_rate: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    fixed_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal(0))
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual | api
    notes: Mapped[str | None] = mapped_column(Text)
