"""Schemas dos cadastros do admin. *In = criação, *Patch = edição parcial, *Out = resposta.

Os mesmos schemas serão usados pelo botão "✨ Enriquecer com IA" (spec 5.5): a IA devolve JSON
validado por eles, então números de custo/medida nunca entram sem passar pelas mesmas regras.
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, computed_field

Hex = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]
Money = Annotated[Decimal, Field(ge=0, max_digits=10, decimal_places=2)]
Rate = Annotated[Decimal, Field(ge=0, lt=1, max_digits=6, decimal_places=4)]
Mm = Annotated[int, Field(gt=0, le=2000)]
MaterialKind = Literal["PLA", "PETG", "ASA", "ABS", "TPU", "PA", "PC", "RESINA"]
PrinterStatus = Literal["ativa", "inativa", "planejada"]


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
    updated_at: datetime


# --- Materiais -------------------------------------------------------------------------------
class MaterialIn(BaseModel):
    kind: MaterialKind
    color_name: Annotated[str, StringConstraints(min_length=1, max_length=60)]
    color_hex: Hex
    brand: str | None = Field(default=None, max_length=80)
    finish: str | None = Field(default=None, max_length=40)
    supplier: str | None = Field(default=None, max_length=120)
    price_per_kg: Money
    density_g_cm3: Decimal | None = Field(default=None, gt=0, le=5, description="vazio = típica")
    stock_grams: int = Field(default=0, ge=0)
    reorder_point_grams: int = Field(default=500, ge=0)
    active: bool = True


class MaterialPatch(BaseModel):
    kind: MaterialKind | None = None
    color_name: str | None = Field(default=None, min_length=1, max_length=60)
    color_hex: Hex | None = None
    brand: str | None = None
    finish: str | None = None
    supplier: str | None = None
    price_per_kg: Money | None = None
    density_g_cm3: Decimal | None = Field(default=None, gt=0, le=5)
    stock_grams: int | None = Field(default=None, ge=0)
    reorder_point_grams: int | None = Field(default=None, ge=0)
    active: bool | None = None


class MaterialOut(_Out, MaterialIn):
    @computed_field  # type: ignore[prop-decorator]
    @property
    def low_stock(self) -> bool:
        """Alerta de reposição (dashboard e WhatsApp nas próximas fases)."""
        return self.stock_grams <= self.reorder_point_grams


# --- Impressoras -----------------------------------------------------------------------------
class PrinterIn(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    model: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    bed_x_mm: Mm
    bed_y_mm: Mm
    bed_z_mm: Mm
    avg_watts: int = Field(gt=0, le=5000)
    hourly_wear: Money
    enclosed: bool = False
    has_ams: bool = False
    supported_materials: list[MaterialKind] = []
    status: PrinterStatus = "ativa"


class PrinterPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    model: str | None = Field(default=None, min_length=1, max_length=80)
    bed_x_mm: Mm | None = None
    bed_y_mm: Mm | None = None
    bed_z_mm: Mm | None = None
    avg_watts: int | None = Field(default=None, gt=0, le=5000)
    hourly_wear: Money | None = None
    enclosed: bool | None = None
    has_ams: bool | None = None
    supported_materials: list[MaterialKind] | None = None
    status: PrinterStatus | None = None


class PrinterOut(_Out, PrinterIn):
    pass


# --- Embalagens ------------------------------------------------------------------------------
class PackagingIn(BaseModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    inner_x_mm: Mm
    inner_y_mm: Mm
    inner_z_mm: Mm
    weight_g: int = Field(gt=0, le=30000)
    cost: Money
    active: bool = True


class PackagingPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    inner_x_mm: Mm | None = None
    inner_y_mm: Mm | None = None
    inner_z_mm: Mm | None = None
    weight_g: int | None = Field(default=None, gt=0, le=30000)
    cost: Money | None = None
    active: bool | None = None


class PackagingOut(_Out, PackagingIn):
    pass


# --- Tarifas por canal -----------------------------------------------------------------------
class FeeBandIn(BaseModel):
    channel: Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{2,40}$")]
    category: str | None = Field(default=None, max_length=120)
    min_price: Money = Decimal(0)
    max_price: Money | None = None
    commission_rate: Rate
    fixed_fee: Money = Decimal(0)
    source: Literal["manual", "api"] = "manual"
    notes: str | None = None


class FeeBandPatch(BaseModel):
    category: str | None = None
    min_price: Money | None = None
    max_price: Money | None = None
    commission_rate: Rate | None = None
    fixed_fee: Money | None = None
    notes: str | None = None


class FeeBandOut(_Out, FeeBandIn):
    pass


# --- Configuração de custos ------------------------------------------------------------------
class CostConfigIn(BaseModel):
    energy_price_kwh: Annotated[Decimal, Field(gt=0, max_digits=8, decimal_places=4)]
    labor_per_hour: Money
    failure_rate: Rate
    min_profit: Money
    default_margin: Annotated[Decimal, Field(ge=0, le=5, max_digits=5, decimal_places=4)]
    margin_by_category: dict[str, Decimal] = {}


class CostConfigOut(CostConfigIn):
    model_config = ConfigDict(from_attributes=True)
    updated_at: datetime
