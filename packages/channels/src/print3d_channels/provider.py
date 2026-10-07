"""Contrato de canal de venda. ML (Fase 3) e Shopee (Fase 4) implementam esta interface.

Tarifas NUNCA ficam no código: vêm da API do canal ou da tabela `ChannelFee`.
"""

from decimal import Decimal
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from print3d_core import SalesChannel


class ListingStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    REJECTED = "rejected"
    CLOSED = "closed"


class ListingDraft(BaseModel):
    variant_id: str
    title: str
    description: str
    price: Decimal = Field(gt=0)
    stock: int = Field(ge=0)
    image_urls: list[str]
    package_weight_g: int = Field(gt=0)  # peso da EMBALAGEM, não só da peça
    package_dimensions_mm: tuple[int, int, int]


class ListingResult(BaseModel):
    external_id: str
    status: ListingStatus
    error: str | None = None


@runtime_checkable
class ChannelProvider(Protocol):
    channel: SalesChannel

    async def publish(self, draft: ListingDraft) -> ListingResult: ...

    async def update_price_and_stock(
        self, external_id: str, *, price: Decimal, stock: int
    ) -> ListingResult: ...

    async def pause(self, external_id: str) -> ListingResult: ...
