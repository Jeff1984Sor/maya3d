"""Nichos configuráveis, licenças de personagens, ajustes do Guardião e auditoria."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from print3d_api.db.base import Base
from print3d_api.models.mixins import IdMixin, TimestampMixin


class Niche(IdMixin, TimestampMixin, Base):
    """Ramo do negócio. Criar um nicho novo é cadastro, não código (spec seção 0)."""

    __tablename__ = "niches"

    slug: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    target_count: Mapped[int] = mapped_column(Integer, default=0)
    voice: Mapped[str | None] = mapped_column(Text)  # voz da marca usada pelos agentes de IA
    categories: Mapped[list[str]] = mapped_column(JSONB, default=list)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class License(IdMixin, TimestampMixin, Base):
    """Licença de personagem/marca de terceiros (spec 2.6). Sem licença vigente: bloqueado."""

    __tablename__ = "licenses"

    licensor: Mapped[str] = mapped_column(String(160))
    covered_terms: Mapped[list[str]] = mapped_column(JSONB, default=list)  # personagens/marcas
    categories: Mapped[list[str]] = mapped_column(JSONB, default=list)  # vazio = todas
    channels: Mapped[list[str]] = mapped_column(JSONB, default=list)  # vazio = todos
    territory: Mapped[str | None] = mapped_column(String(80))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date] = mapped_column(Date)
    royalty_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    royalty_per_unit: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    approval_rules: Mapped[str | None] = mapped_column(Text)
    contract_url: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class GuardianTermOverride(IdMixin, TimestampMixin, Base):
    """Ajuste do admin sobre as regras padrão: acrescentar ou remover um termo."""

    __tablename__ = "guardian_term_overrides"

    term: Mapped[str] = mapped_column(String(120))
    mode: Mapped[str] = mapped_column(String(10))  # add | remove
    rule_code: Mapped[str | None] = mapped_column(String(60))  # remove sem código = todas
    reason: Mapped[str | None] = mapped_column(Text)


class AuditLog(IdMixin, Base):
    """Toda decisão automática (publicou, bloqueou, mudou preço, respondeu) com motivo.
    Só inserção: nunca atualizar nem apagar."""

    __tablename__ = "audit_log"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    actor: Mapped[str] = mapped_column(String(40))  # guardiao | precificador | admin | ...
    action: Mapped[str] = mapped_column(String(60))
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(60))
    decision: Mapped[str | None] = mapped_column(String(40))
    reason: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
