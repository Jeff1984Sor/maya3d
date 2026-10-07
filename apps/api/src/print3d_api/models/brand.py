"""Identidade da marca em UMA linha editável (spec seção 0.1). Nada de nome fixo no código."""

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from print3d_api.db.base import Base

SINGLETON_ID = 1


class BrandSettings(Base):
    __tablename__ = "brand_settings"
    __table_args__ = (CheckConstraint(f"id = {SINGLETON_ID}", name="singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=SINGLETON_ID)
    name: Mapped[str] = mapped_column(String(120))
    tagline: Mapped[str | None] = mapped_column(String(240))
    logo_light_url: Mapped[str | None] = mapped_column(Text)
    logo_dark_url: Mapped[str | None] = mapped_column(Text)
    favicon_url: Mapped[str | None] = mapped_column(Text)
    # {"light": {"bg": "#...", ...}, "dark": {...}} — tokens da seção 5.1
    colors: Mapped[dict[str, dict[str, str]]] = mapped_column(JSONB)
    fonts: Mapped[dict[str, str]] = mapped_column(JSONB)
    domain: Mapped[str | None] = mapped_column(String(255))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_whatsapp: Mapped[str | None] = mapped_column(String(32))
    social: Mapped[dict[str, str]] = mapped_column(JSONB, default=dict)
    cnpj: Mapped[str | None] = mapped_column(String(18))
    legal_name: Mapped[str | None] = mapped_column(String(255))
    voice: Mapped[str | None] = mapped_column(Text)  # instrução global para os agentes de IA
    voice_by_niche: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
