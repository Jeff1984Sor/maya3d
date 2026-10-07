"""Schemas públicos da loja: nada de custo, margem, autor de licença interno ou dados de outros
clientes."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, EmailStr, Field, StringConstraints


class StoreNiche(BaseModel):
    slug: str
    name: str
    products: int


class ColorOption(BaseModel):
    material_id: int
    name: str
    hex: str
    kind: str


class StoreVariant(BaseModel):
    id: int
    sku: str
    label: str
    finish: str
    price_pix: Decimal | None
    price_card: Decimal | None
    colors: list[ColorOption]


class StoreProductCard(BaseModel):
    slug: str
    title: str
    niche: str
    category: str
    customizable: bool
    price_from: Decimal | None
    colors: list[str]  # hex para as bolinhas abaixo do preço
    image: str | None = None  # miniatura da capa (/m/...)


class StoreImage(BaseModel):
    url: str
    thumb: str
    alt: str | None


class StoreProduct(StoreProductCard):
    description: str | None
    tags: list[str]
    disclaimers: list[str]
    attribution: str | None
    age_rating: str | None
    variants: list[StoreVariant]
    parametric_model: str | None  # quando o produto tem personalizador 3D
    images: list[StoreImage] = []


class CartLineIn(BaseModel):
    variant_id: int
    quantity: int = Field(ge=1, le=999)
    material_id: int | None = None
    personalization: dict[str, Annotated[str, StringConstraints(max_length=60)]] = {}


class CartIn(BaseModel):
    items: list[CartLineIn] = Field(max_length=50)


class CartLine(BaseModel):
    variant_id: int
    product_slug: str
    title: str
    quantity: int
    material_id: int | None
    color: ColorOption | None
    personalization: dict[str, str]
    unit_price: Decimal | None
    line_total: Decimal | None


class CartOut(BaseModel):
    token: str
    items: list[CartLine]
    subtotal: Decimal
    purchasable: bool
    problems: list[str] = []


SHIPPING_OPTION = r"^(local|retirada|envio|me-\d{1,6})$"


class ShippingOption(BaseModel):
    id: Annotated[str, StringConstraints(pattern=SHIPPING_OPTION)]  # me-<serviço> = Melhor Envio
    label: str
    price: Decimal | None  # None = valor combinado depois (frete automático indisponível)
    detail: str = ""


class ShippingQuote(BaseModel):
    cep: str
    city: str
    uf: str
    local: bool
    options: list[ShippingOption]
    free_shipping_min: Decimal | None = None
    missing_for_free: Decimal | None = None  # "faltam R$ X para o frete grátis"


class ShippingIn(BaseModel):
    cep: str
    subtotal: Decimal = Field(ge=0)
    cart_token: str | None = None  # com o carrinho, a cotação usa medidas e peso reais


class CheckoutIn(BaseModel):
    cart_token: str
    name: Annotated[str, StringConstraints(min_length=2, max_length=160)]
    email: EmailStr
    whatsapp: Annotated[str, StringConstraints(min_length=10, max_length=20)]
    whatsapp_opt_in: bool = False
    marketing_opt_in: bool = False
    accept_terms: bool
    cep: str
    street: Annotated[str, StringConstraints(min_length=2, max_length=160)]
    number: Annotated[str, StringConstraints(min_length=1, max_length=20)]
    complement: str | None = Field(default=None, max_length=80)
    district: str = Field(default="", max_length=80)
    shipping_option: Annotated[str, StringConstraints(pattern=SHIPPING_OPTION)]
    notes: str | None = Field(default=None, max_length=500)


class PixInstructions(BaseModel):
    key: str | None
    name: str | None
    amount: Decimal


class CheckoutOut(BaseModel):
    order_number: int
    public_token: str
    total: Decimal
    shipping_pending: bool
    pix: PixInstructions


class TimelineEntry(BaseModel):
    at: datetime
    status: str
    label: str
    media_url: str | None = None


class PublicOrder(BaseModel):
    number: int
    status: str
    status_label: str
    total: Decimal
    shipping: Decimal
    items: list[dict[str, Any]]
    timeline: list[TimelineEntry]
    progress: str
    pix: PixInstructions | None = None
