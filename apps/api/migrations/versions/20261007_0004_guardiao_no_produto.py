"""resultado do Guardião gravado no produto

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # expand: colunas novas com default; nada removido
    op.add_column(
        "products",
        sa.Column("guardian_status", sa.String(20), nullable=False, server_default="pendente"),
    )
    op.add_column("products", sa.Column("guardian_reason", sa.Text()))
    op.add_column(
        "products",
        sa.Column("disclaimers", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "products",
        sa.Column("attribution_required", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    for col in ("attribution_required", "disclaimers", "guardian_reason", "guardian_status"):
        op.drop_column("products", col)
