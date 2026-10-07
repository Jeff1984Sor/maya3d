"""redator por canal e busca semântica (vetores dos produtos)

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "product_embeddings",
        sa.Column("product_id", sa.Integer(), primary_key=True),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(), nullable=False),
        *_ts(),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_product_embeddings_product_id_products"),
            ondelete="CASCADE",
        ),
    )
    op.create_table(
        "channel_copies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("bullets", JSONB, nullable=False, server_default="[]"),
        sa.Column("keywords", JSONB, nullable=False, server_default="[]"),
        sa.Column("hashtags", JSONB, nullable=False, server_default="[]"),
        sa.Column("status", sa.String(20), nullable=False, server_default="rascunho"),
        sa.Column("guardian_status", sa.String(20), nullable=False),
        sa.Column("issues", JSONB, nullable=False, server_default="[]"),
        sa.Column("model", sa.String(80)),
        sa.Column("prompt_version", sa.String(40)),
        *_ts(),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_channel_copies_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("product_id", "channel", name=op.f("uq_channel_copies_product_id")),
    )
    op.create_index(op.f("ix_channel_copies_product_id"), "channel_copies", ["product_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_channel_copies_product_id"), table_name="channel_copies")
    op.drop_table("channel_copies")
    op.drop_table("product_embeddings")
