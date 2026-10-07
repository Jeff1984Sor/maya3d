"""biblioteca de modelos (acervos enviados pelo painel)

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0012"
down_revision: str | None = "0011"
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
        "library_collections",
        sa.Column("slug", sa.String(80), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("niche", sa.String(40), nullable=False),
        sa.Column("license_text", sa.Text()),
        sa.Column("status", sa.String(20), nullable=False, server_default="vazio"),
        sa.Column("error", sa.Text()),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        *_ts(),
    )
    op.create_table(
        "library_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("collection_slug", sa.String(80), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("files", JSONB, nullable=False, server_default="[]"),
        sa.Column("cover", sa.String(200)),
        sa.Column("bbox_mm", JSONB),
        sa.Column("fits", sa.Boolean()),
        sa.Column("issues", JSONB, nullable=False, server_default="[]"),
        sa.Column("status", sa.String(20), nullable=False, server_default="novo"),
        sa.Column("product_id", sa.Integer()),
        *_ts(),
        sa.ForeignKeyConstraint(
            ["collection_slug"],
            ["library_collections.slug"],
            name=op.f("fk_library_models_collection_slug_library_collections"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "collection_slug", "key", name=op.f("uq_library_models_collection_slug")
        ),
    )
    op.create_index(
        op.f("ix_library_models_collection_slug"), "library_models", ["collection_slug"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_library_models_collection_slug"), table_name="library_models")
    op.drop_table("library_models")
    op.drop_table("library_collections")
