"""guardião visual: resultado da análise de cada foto de produto

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "product_images",
        sa.Column("visual_status", sa.String(20), nullable=False, server_default="pendente"),
    )
    op.add_column(
        "product_images",
        sa.Column("visual_notes", JSONB, nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("product_images", "visual_notes")
    op.drop_column("product_images", "visual_status")
