"""configuração de IA editável no painel (modelos por tarefa, limite diário)

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    ai = op.create_table(
        "ai_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_default", sa.String(80)),
        sa.Column("model_guardian", sa.String(80)),
        sa.Column("model_personalizer", sa.String(80)),
        sa.Column("model_embedding", sa.String(80)),
        sa.Column("daily_budget_usd", sa.Numeric(10, 2), nullable=False, server_default="5"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("id = 1", name=op.f("ck_ai_config_singleton")),
    )
    # Sem modelo pré-escolhido: o dono escolhe no painel entre os modelos que a conta oferece.
    op.bulk_insert(ai, [{"id": 1, "daily_budget_usd": 5}])


def downgrade() -> None:
    op.drop_table("ai_config")
