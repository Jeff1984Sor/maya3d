"""Catálogo: Design (projeto/licença) → Product (vendável) → Variant (tamanho/cor/parâmetros).

Embedding do produto (pgvector) entra na Fase 6, quando o modelo de embedding estiver definido
(a dimensão do vetor depende dele).
"""

from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from print3d_api.db.base import Base
from print3d_api.models.mixins import IdMixin, TimestampMixin


class Design(IdMixin, TimestampMixin, Base):
    __tablename__ = "designs"

    name: Mapped[str] = mapped_column(String(160))
    # parametrico | licenca_comercial | cc0 | cc_by
    origin: Mapped[str] = mapped_column(String(30))
    author: Mapped[str | None] = mapped_column(String(160))
    license: Mapped[str] = mapped_column(String(80))
    source_url: Mapped[str | None] = mapped_column(Text)
    attribution_required: Mapped[bool] = mapped_column(Boolean, default=False)
    attribution_text: Mapped[str | None] = mapped_column(Text)
    source_file_url: Mapped[str | None] = mapped_column(Text)
    params_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # pendente | aprovado | bloqueado — decidido pelo Guardião de IP (Fase 2), nunca à mão
    ip_status: Mapped[str] = mapped_column(String(20), default="pendente")
    ip_reason: Mapped[str | None] = mapped_column(Text)
    printability_notes: Mapped[str | None] = mapped_column(Text)


class Product(IdMixin, TimestampMixin, Base):
    __tablename__ = "products"

    design_id: Mapped[int] = mapped_column(ForeignKey("designs.id"), index=True)
    niche: Mapped[str] = mapped_column(String(40))
    category: Mapped[str] = mapped_column(String(120))
    subcategory: Mapped[str | None] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(220), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    occasions: Mapped[list[str]] = mapped_column(JSONB, default=list)
    age_rating: Mapped[str | None] = mapped_column(String(20))
    # material mínimo por uso (ex.: ASA para painel de carro). Sem impressora capaz → indisponível.
    min_material: Mapped[str | None] = mapped_column(String(20))
    customizable: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="rascunho")


class Variant(IdMixin, TimestampMixin, Base):
    __tablename__ = "variants"

    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    sku: Mapped[str] = mapped_column(String(80), unique=True)
    size_label: Mapped[str | None] = mapped_column(String(40))
    finish: Mapped[str] = mapped_column(String(20), default="cor_unica")  # cor_unica | pintada
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    color_by_part: Mapped[dict[str, int]] = mapped_column(JSONB, default=dict)  # parte → material
    dims_mm: Mapped[list[float] | None] = mapped_column(JSONB)
    # Vêm do fatiador. Sem fatiar: slicing_source = "a_confirmar" e não há preço.
    grams_by_material: Mapped[dict[str, float] | None] = mapped_column(JSONB)
    print_seconds: Mapped[int | None] = mapped_column(Integer)
    slicing_source: Mapped[str] = mapped_column(String(20), default="a_confirmar")
    post_minutes: Mapped[int] = mapped_column(Integer, default=0)
    packaging_id: Mapped[int | None] = mapped_column(ForeignKey("packaging_boxes.id"))
    packed_weight_g: Mapped[int | None] = mapped_column(Integer)
