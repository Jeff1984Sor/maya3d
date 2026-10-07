"""Biblioteca de modelos: acervos que o dono enviou pelo painel, organizados pelo worker."""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from print3d_api.db.base import Base
from print3d_api.models.mixins import IdMixin, TimestampMixin


class LibraryCollection(TimestampMixin, Base):
    """Um acervo (pacote comprado, coleção própria). A licença declarada vale para todos."""

    __tablename__ = "library_collections"

    slug: Mapped[str] = mapped_column(String(80), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(120))
    niche: Mapped[str] = mapped_column(String(40))
    # Texto da licença (ex.: "licença comercial — compra de 07/10/2026"). Vazio = produtos
    # ficam bloqueados pelo Guardião até o dono confirmar o direito de vender.
    license_text: Mapped[str | None] = mapped_column(Text)
    # vazio | processando | pronto | erro
    status: Mapped[str] = mapped_column(String(20), default="vazio")
    error: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LibraryModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "library_models"
    __table_args__ = (UniqueConstraint("collection_slug", "key"),)

    collection_slug: Mapped[str] = mapped_column(
        ForeignKey("library_collections.slug", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(200))
    files: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    cover: Mapped[str | None] = mapped_column(String(200))
    bbox_mm: Mapped[list[float] | None] = mapped_column(JSONB)
    fits: Mapped[bool | None] = mapped_column(Boolean)
    issues: Mapped[list[str]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(20), default="novo")  # novo | produto | ignorado
    product_id: Mapped[int | None] = mapped_column(Integer)
