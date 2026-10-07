"""Conteúdo da loja editável no painel: fotos de produto, página inicial e páginas."""

from typing import Any

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from print3d_api.db.base import Base
from print3d_api.models.mixins import IdMixin, TimestampMixin

STORE_LAYOUT_ID = 1


class ProductImage(IdMixin, TimestampMixin, Base):
    __tablename__ = "product_images"

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(200))
    thumb_key: Mapped[str] = mapped_column(String(200))
    alt: Mapped[str | None] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer, default=0)  # 0 = capa


class StoreLayout(TimestampMixin, Base):
    """Página inicial: faixa de aviso, destaque e vitrines (singleton)."""

    __tablename__ = "store_layout"
    __table_args__ = (CheckConstraint(f"id = {STORE_LAYOUT_ID}", name="singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=STORE_LAYOUT_ID)
    announcement: Mapped[str | None] = mapped_column(String(200))
    # {"title", "subtitle", "image_key", "cta_label", "cta_href"}
    hero: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    # [{"title", "kind": newest|niche|category|tag|manual, "value", "limit"}]
    sections: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)


class StorePage(TimestampMixin, Base):
    """Páginas institucionais (sobre, trocas, privacidade...). Texto em Markdown simples."""

    __tablename__ = "store_pages"

    slug: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    in_footer: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
