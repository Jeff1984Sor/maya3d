from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]


class QuoteRequest(BaseModel):
    """Gramas e tempo vêm do fatiador. Enquanto não houver fatiador, o dono informa (manual)."""

    grams_by_material: dict[int, Annotated[Decimal, Field(ge=0, le=20000)]] = Field(min_length=1)
    print_minutes: int = Field(gt=0, le=60 * 24 * 7)
    printer_id: int
    post_minutes: int = Field(default=0, ge=0, le=60 * 24)
    category: str | None = None
    extra_costs: Money = Decimal(0)
    shipping_by_channel: dict[str, Money] = {}
    channels: list[str] | None = None  # None = todos os canais com tarifa cadastrada


class CostOut(BaseModel):
    material: Decimal
    energy: Decimal
    wear: Decimal
    labor: Decimal
    failure: Decimal
    extras: Decimal
    total: Decimal


class ChannelQuoteOut(BaseModel):
    channel: str
    price: Decimal | None = None
    commission: Decimal | None = None
    fixed_fee: Decimal | None = None
    shipping: Decimal = Decimal(0)
    net_profit: Decimal | None = None
    margin_pct: Decimal | None = None  # lucro / preço
    error: str | None = None


class QuoteResponse(BaseModel):
    cost: CostOut
    target_profit: Decimal
    quotes: list[ChannelQuoteOut]
    warnings: list[str] = []


class CompareRequest(BaseModel):
    """Mesma peça em vários materiais. Gramas e tempo são do material de referência."""

    reference_material_id: int | None = None
    reference_kind: str = "PLA"  # usado se não houver material de referência
    grams: Annotated[Decimal, Field(gt=0, le=20000)]
    print_minutes: int = Field(gt=0, le=60 * 24 * 7)
    printer_id: int
    post_minutes: int = Field(default=0, ge=0, le=60 * 24)
    category: str | None = None
    extra_costs: Money = Decimal(0)
    channels: list[str] | None = None
    material_ids: list[int] | None = None  # None = todos os materiais ativos


class CompareRow(BaseModel):
    material_id: int
    label: str
    kind: str
    color_hex: str
    density: Decimal
    grams: Decimal
    cost: CostOut
    quotes: list[ChannelQuoteOut]
    warnings: list[str] = []
    best_price: Decimal | None = None
    best_profit: Decimal | None = None


class CompareResponse(BaseModel):
    reference: str
    reference_grams: Decimal
    rows: list[CompareRow]
