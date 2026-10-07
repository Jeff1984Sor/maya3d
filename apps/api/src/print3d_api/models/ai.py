from decimal import Decimal

from sqlalchemy import CheckConstraint, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from print3d_api.db.base import Base
from print3d_api.models.mixins import TimestampMixin

AI_CONFIG_ID = 1


class AIConfig(TimestampMixin, Base):
    """Modelos por tarefa escolhidos no painel (sobrepõem AI_MODEL_* do ambiente).
    A chave e o fornecedor ficam só no .env do servidor, nunca no banco."""

    __tablename__ = "ai_config"
    __table_args__ = (CheckConstraint(f"id = {AI_CONFIG_ID}", name="singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=AI_CONFIG_ID)
    model_default: Mapped[str | None] = mapped_column(String(80))
    model_guardian: Mapped[str | None] = mapped_column(String(80))
    model_personalizer: Mapped[str | None] = mapped_column(String(80))
    model_embedding: Mapped[str | None] = mapped_column(String(80))
    daily_budget_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal(5))
