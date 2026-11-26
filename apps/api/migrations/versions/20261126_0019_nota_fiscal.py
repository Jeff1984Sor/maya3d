"""nota fiscal própria (NF-e): tabela de notas e NCM por produto

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # expand: tabela nova e coluna opcional; a versão anterior ignora as duas
    op.add_column("products", sa.Column("ncm", sa.String(8), nullable=True))
    op.create_table(
        "fiscal_invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("ambiente", sa.Integer(), nullable=False),
        sa.Column("serie", sa.Integer(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("chave", sa.String(44), nullable=True),
        sa.Column("cstat", sa.String(4), nullable=True),
        sa.Column("motivo", sa.Text(), nullable=True),
        sa.Column("protocolo", sa.String(20), nullable=True),
        sa.Column("total", sa.Numeric(10, 2), nullable=False),
        sa.Column("recipient", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("xml", sa.Text(), nullable=True),
        sa.Column("proc_xml", sa.Text(), nullable=True),
        sa.Column("cancel_xml", sa.Text(), nullable=True),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ml_status", sa.Text(), nullable=True),
        sa.Column("email_status", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name=op.f("fk_fiscal_invoices_order_id_orders")
        ),
        sa.UniqueConstraint("ambiente", "serie", "number", name=op.f("uq_nfe_numero")),
        sa.UniqueConstraint("chave", name=op.f("uq_fiscal_invoices_chave")),
    )
    op.create_index(op.f("ix_fiscal_invoices_order_id"), "fiscal_invoices", ["order_id"])
    op.create_index(op.f("ix_fiscal_invoices_status"), "fiscal_invoices", ["status"])


def downgrade() -> None:
    op.drop_table("fiscal_invoices")
    op.drop_column("products", "ncm")
