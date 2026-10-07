"""Produtos, designs e variantes (spec 5.5 — cadastro de produto)."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Origin = Literal["parametrico", "licenca_comercial", "cc0", "cc_by", "outro"]
ProductStatus = Literal["rascunho", "ativo", "pausado"]
Finish = Literal["cor_unica", "pintada"]
SlicingSource = Literal["a_confirmar", "manual", "fatiador"]
Text = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class DesignIn(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    origin: Origin = "parametrico"
    author: str | None = Field(default=None, max_length=160)
    license: str = Field(default="próprio", max_length=80)
    source_url: str | None = None
    attribution_text: str | None = None
    source_file_url: str | None = None
    params_schema: dict[str, Any] = {}
    printability_notes: str | None = None


class DesignOut(DesignIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    attribution_required: bool
    ip_status: str
    ip_reason: str | None


class ProductBase(BaseModel):
    niche: str
    category: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    subcategory: str | None = Field(default=None, max_length=120)
    title: Text
    description: str | None = None
    tags: list[str] = []
    occasions: list[str] = []
    min_material: str | None = Field(default=None, max_length=20)
    customizable: bool = False


class ProductCreate(ProductBase):
    design: DesignIn


class ProductPatch(BaseModel):
    niche: str | None = None
    category: str | None = Field(default=None, min_length=1, max_length=120)
    subcategory: str | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    tags: list[str] | None = None
    occasions: list[str] | None = None
    min_material: str | None = None
    customizable: bool | None = None
    status: ProductStatus | None = None
    design: DesignIn | None = None


class VariantIn(BaseModel):
    sku: str | None = Field(default=None, max_length=80, description="vazio = automático")
    size_label: str | None = Field(default=None, max_length=40)
    finish: Finish = "cor_unica"
    params: dict[str, Any] = {}
    color_by_part: dict[str, int] = {}
    dims_mm: list[float] | None = Field(default=None, min_length=3, max_length=3)
    grams_by_material: dict[str, float] | None = None
    print_seconds: int | None = Field(default=None, ge=0)
    post_minutes: int = Field(default=0, ge=0)
    packaging_id: int | None = None
    packed_weight_g: int | None = Field(default=None, gt=0)


class VariantPatch(BaseModel):
    size_label: str | None = None
    finish: Finish | None = None
    params: dict[str, Any] | None = None
    color_by_part: dict[str, int] | None = None
    dims_mm: list[float] | None = Field(default=None, min_length=3, max_length=3)
    grams_by_material: dict[str, float] | None = None
    print_seconds: int | None = Field(default=None, ge=0)
    post_minutes: int | None = Field(default=None, ge=0)
    packaging_id: int | None = None
    packed_weight_g: int | None = Field(default=None, gt=0)


class VariantOut(VariantIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    sku: str
    slicing_source: SlicingSource
    created_at: datetime


class ProductSummary(ProductBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    slug: str
    status: ProductStatus
    guardian_status: str
    guardian_reason: str | None
    age_rating: str | None
    updated_at: datetime
    variant_count: int = 0
    available: bool = True  # há impressora capaz do material mínimo?


class ProductDetail(ProductSummary):
    design: DesignOut
    variants: list[VariantOut]
    disclaimers: list[str]
    attribution_required: bool


class VariantQuoteOut(BaseModel):
    """Preço da variante por canal; sem gramas/tempo = 'a confirmar' (a IA nunca chuta)."""

    ready: bool
    reason: str | None = None
    cost_total: Decimal | None = None
    quotes: list[dict[str, Any]] = []
    warnings: list[str] = []
