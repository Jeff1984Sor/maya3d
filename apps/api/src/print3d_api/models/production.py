"""Insumos e máquinas: materiais (filamentos), impressoras e embalagens (spec seções 1 e 5.5)."""

from decimal import Decimal

from sqlalchemy import Boolean, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from print3d_api.db.base import Base
from print3d_api.models.mixins import IdMixin, TimestampMixin


class Material(IdMixin, TimestampMixin, Base):
    __tablename__ = "materials"

    kind: Mapped[str] = mapped_column(String(20))  # PLA, PETG, ASA, TPU...
    color_name: Mapped[str] = mapped_column(String(60))
    color_hex: Mapped[str] = mapped_column(String(7))
    brand: Mapped[str | None] = mapped_column(String(80))
    finish: Mapped[str | None] = mapped_column(String(40))  # silk, matte...
    supplier: Mapped[str | None] = mapped_column(String(120))
    price_per_kg: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # Nulo = densidade típica do tipo (print3d_core.materials). Usada no comparativo.
    density_g_cm3: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    stock_grams: Mapped[int] = mapped_column(Integer, default=0)
    reorder_point_grams: Mapped[int] = mapped_column(Integer, default=500)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Printer(IdMixin, TimestampMixin, Base):
    """Cadastrada pelo dono quando a máquina existir; nada de impressora fixa no código."""

    __tablename__ = "printers"

    name: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(80))
    bed_x_mm: Mapped[int] = mapped_column(Integer)
    bed_y_mm: Mapped[int] = mapped_column(Integer)
    bed_z_mm: Mapped[int] = mapped_column(Integer)
    avg_watts: Mapped[int] = mapped_column(Integer)
    hourly_wear: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # R$/h de desgaste
    enclosed: Mapped[bool] = mapped_column(Boolean, default=False)  # ASA exige fechada
    has_ams: Mapped[bool] = mapped_column(Boolean, default=False)
    supported_materials: Mapped[list[str]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(20), default="ativa")  # ativa|inativa|planejada


class PackagingBox(IdMixin, TimestampMixin, Base):
    """Embalagem: peso e medidas EMBALADOS vão para frete e tarifas dos marketplaces."""

    __tablename__ = "packaging_boxes"

    name: Mapped[str] = mapped_column(String(80))
    inner_x_mm: Mapped[int] = mapped_column(Integer)
    inner_y_mm: Mapped[int] = mapped_column(Integer)
    inner_z_mm: Mapped[int] = mapped_column(Integer)
    weight_g: Mapped[int] = mapped_column(Integer)
    cost: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
