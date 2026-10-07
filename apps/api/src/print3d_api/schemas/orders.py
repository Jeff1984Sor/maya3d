from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Channel = Literal["site", "mercadolivre", "shopee", "manual"]


class CustomerIn(BaseModel):
    kind: Literal["pf", "pj"] = "pf"
    name: str = Field(min_length=1, max_length=160)
    legal_name: str | None = None
    document: str | None = Field(default=None, max_length=20)
    email: str | None = None
    whatsapp: str | None = Field(default=None, max_length=32)
    whatsapp_opt_in: bool = False
    marketing_opt_in: bool = False
    source: str | None = None
    segment: str | None = None
    notes: str | None = None


class CustomerPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    legal_name: str | None = None
    document: str | None = None
    email: str | None = None
    whatsapp: str | None = None
    whatsapp_opt_in: bool | None = None
    marketing_opt_in: bool | None = None
    segment: str | None = None
    notes: str | None = None


class CustomerOut(CustomerIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


class OrderItemIn(BaseModel):
    variant_id: int | None = None
    title: str | None = Field(default=None, max_length=200, description="vazio = da variante")
    quantity: int = Field(gt=0, le=10000)
    unit_price: Decimal = Field(ge=0)
    personalization: dict[str, Any] = {}
    material_ids: list[int] = []


class OrderCreate(BaseModel):
    """Venda vinda de qualquer canal (ou lançada à mão para B2B/teste)."""

    channel: Channel = "manual"
    external_id: str | None = None
    customer_id: int | None = None
    items: list[OrderItemIn] = Field(min_length=1)
    shipping: Decimal = Field(default=Decimal(0), ge=0)
    discount: Decimal = Field(default=Decimal(0), ge=0)
    shipping_address: dict[str, Any] | None = None
    local_delivery: bool = False
    promised_date: date | None = None
    notes: str | None = None


class AdvanceIn(BaseModel):
    to: str
    note: str | None = None
    media_url: str | None = None


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    variant_id: int | None
    title: str
    sku: str | None
    quantity: int
    unit_price: Decimal
    personalization: dict[str, Any]
    material_ids: list[int]
    needs_sample: bool
    produced: int


class OrderEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime
    status: str
    note: str | None
    media_url: str | None
    actor: str


class PrintJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_item_id: int
    quantity: int
    is_sample: bool
    status: str
    material_key: str
    due_date: date | None
    printer_id: int | None
    failure_reason: str | None


class OrderSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    number: int
    channel: str
    status: str
    total: Decimal
    customer_id: int | None
    promised_date: date | None
    local_delivery: bool
    created_at: datetime
    progress: str = ""  # "7 de 25 impressas"
    next_step: str | None = None


class OrderDetail(OrderSummary):
    payment_method: str | None = None
    public_token: str | None = None
    subtotal: Decimal
    shipping: Decimal
    discount: Decimal
    sample_rounds: int
    notes: str | None
    shipping_address: dict[str, Any] | None
    items: list[OrderItemOut]
    events: list[OrderEventOut]
    jobs: list[PrintJobOut]
    allowed: list[str]
    customer: CustomerOut | None = None


class QueueGroup(BaseModel):
    """Fila agrupada por material/cor para reduzir trocas de filamento."""

    material_key: str
    materials: list[str]
    jobs: list[dict[str, Any]]
    total_pieces: int


class OpsConfigIn(BaseModel):
    sample_threshold: int = Field(ge=1, le=10000)
    free_sample_rounds: int = Field(ge=0, le=20)
    sample_reminder_hours: list[int] = []
    local_free_shipping_min: Decimal = Field(ge=0)
    local_cities_ibge: list[str] = []
    local_delivery_fee: Decimal = Field(ge=0)
    pickup_enabled: bool = False
    owner_whatsapp: str | None = Field(default=None, max_length=32)
    pix_key: str | None = Field(default=None, max_length=140)
    pix_name: str | None = Field(default=None, max_length=100)


class OpsConfigOut(OpsConfigIn):
    model_config = ConfigDict(from_attributes=True)
    updated_at: datetime


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    channel: str
    audience: str
    to: str | None
    template: str
    body: str
    status: str
    attempts: int
    last_error: str | None
    order_id: int | None
