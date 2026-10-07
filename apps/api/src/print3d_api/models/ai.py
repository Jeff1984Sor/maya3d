from decimal import Decimal

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from print3d_api.db.base import Base
from print3d_api.models.mixins import IdMixin, TimestampMixin

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


class ProductEmbedding(TimestampMixin, Base):
    """Vetor do produto para a busca semântica. Sem dimensão fixa: depende do modelo escolhido
    no painel; a busca só compara vetores do mesmo `model`. (Catálogo pequeno: varredura exata,
    sem índice aproximado.)"""

    __tablename__ = "product_embeddings"

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    model: Mapped[str] = mapped_column(String(80))
    content_hash: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[list[float]] = mapped_column(Vector())


class ChannelCopy(IdMixin, TimestampMixin, Base):
    """Texto sugerido pelo Redator para um canal. Só vale depois que o dono aprova."""

    __tablename__ = "channel_copies"
    __table_args__ = (UniqueConstraint("product_id", "channel"),)

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    channel: Mapped[str] = mapped_column(String(20))  # site | mercadolivre | shopee | instagram
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    bullets: Mapped[list[str]] = mapped_column(JSONB, default=list)
    keywords: Mapped[list[str]] = mapped_column(JSONB, default=list)
    hashtags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # rascunho | aprovado | descartado
    status: Mapped[str] = mapped_column(String(20), default="rascunho")
    guardian_status: Mapped[str] = mapped_column(String(20))
    issues: Mapped[list[str]] = mapped_column(JSONB, default=list)  # avisos para o dono revisar
    model: Mapped[str | None] = mapped_column(String(80))
    prompt_version: Mapped[str | None] = mapped_column(String(40))
