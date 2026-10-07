"""marketplaces: conta conectada (tokens cifrados), anúncios e perguntas

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0016"
down_revision: str | None = "0015"
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
        "channel_accounts",
        sa.Column("channel", sa.String(30), primary_key=True),
        sa.Column("external_user_id", sa.String(40), nullable=False),
        sa.Column("nickname", sa.String(120)),
        sa.Column("access_token_enc", sa.Text(), nullable=False),
        sa.Column("refresh_token_enc", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="conectada"),
        *_ts(),
    )
    op.create_table(
        "channel_listings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("variant_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("external_id", sa.String(40)),
        sa.Column("category_id", sa.String(40)),
        sa.Column("listing_type", sa.String(30)),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="rascunho"),
        sa.Column("permalink", sa.Text()),
        sa.Column("last_error", sa.Text()),
        sa.Column("fee", sa.Numeric(10, 2)),
        *_ts(),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_channel_listings_product_id_products"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["variants.id"],
            name=op.f("fk_channel_listings_variant_id_variants"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("external_id", name=op.f("uq_channel_listings_external_id")),
    )
    op.create_index(op.f("ix_channel_listings_product_id"), "channel_listings", ["product_id"])
    op.create_table(
        "marketplace_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("external_id", sa.String(40), nullable=False),
        sa.Column("item_external_id", sa.String(40)),
        sa.Column("product_id", sa.Integer()),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pendente"),
        sa.Column("answer", sa.Text()),
        sa.Column("raw", JSONB, nullable=False, server_default="{}"),
        *_ts(),
        sa.UniqueConstraint("external_id", name=op.f("uq_marketplace_questions_external_id")),
    )


def downgrade() -> None:
    op.drop_table("marketplace_questions")
    op.drop_index(op.f("ix_channel_listings_product_id"), table_name="channel_listings")
    op.drop_table("channel_listings")
    op.drop_table("channel_accounts")
