"""densidade por material (comparativo da mesma peça em materiais diferentes)

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # expand: nulo = usa a densidade típica do tipo (print3d_core.materials)
    op.add_column("materials", sa.Column("density_g_cm3", sa.Numeric(5, 3)))


def downgrade() -> None:
    op.drop_column("materials", "density_g_cm3")
