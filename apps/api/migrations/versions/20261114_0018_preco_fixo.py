"""preço fixo (Pix) por variante — o dono define; nunca abaixo do custo

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # expand: coluna opcional, a versão anterior ignora
    op.add_column("variants", sa.Column("price_override", sa.Numeric(10, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("variants", "price_override")
