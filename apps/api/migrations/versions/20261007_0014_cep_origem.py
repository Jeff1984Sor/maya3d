"""CEP de origem dos envios (cotação de frete)

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ops_config", sa.Column("origin_cep", sa.String(9)))


def downgrade() -> None:
    op.drop_column("ops_config", "origin_cep")
