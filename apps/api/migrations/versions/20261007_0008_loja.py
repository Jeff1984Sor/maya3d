"""loja: carrinho, link público do pedido e forma de pagamento

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ops_config", sa.Column("pix_key", sa.String(140)))
    op.add_column("ops_config", sa.Column("pix_name", sa.String(100)))
    op.add_column("orders", sa.Column("payment_method", sa.String(20)))
    op.add_column("orders", sa.Column("public_token", sa.String(40)))
    op.create_unique_constraint(op.f("uq_orders_public_token"), "orders", ["public_token"])
    op.create_table(
        "carts",
        sa.Column("token", sa.String(40), primary_key=True),
        sa.Column("items", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("cep", sa.String(9)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("carts")
    op.drop_constraint(op.f("uq_orders_public_token"), "orders", type_="unique")
    op.drop_column("orders", "public_token")
    op.drop_column("orders", "payment_method")
    op.drop_column("ops_config", "pix_name")
    op.drop_column("ops_config", "pix_key")
