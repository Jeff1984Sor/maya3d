"""clientes, pedidos, itens, linha do tempo, fila de impressão, amostras, notificações, config de operação

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB()


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
    ops = op.create_table(
        "ops_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sample_threshold", sa.Integer(), nullable=False),
        sa.Column("free_sample_rounds", sa.Integer(), nullable=False),
        sa.Column("sample_reminder_hours", JSONB, nullable=False, server_default="[]"),
        sa.Column("local_free_shipping_min", sa.Numeric(10, 2), nullable=False),
        sa.Column("local_cities_ibge", JSONB, nullable=False, server_default="[]"),
        sa.Column("local_delivery_fee", sa.Numeric(10, 2), nullable=False),
        sa.Column("pickup_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("owner_whatsapp", sa.String(32)),
        *_ts(),
        sa.CheckConstraint("id = 1", name=op.f("ck_ops_config_singleton")),
    )
    # Regras da spec: amostra acima de 10 un.; frete grátis em Sorocaba (IBGE 3552205) ≥ R$ 100.
    op.bulk_insert(
        ops,
        [
            {
                "id": 1,
                "sample_threshold": 10,
                "free_sample_rounds": 2,
                "sample_reminder_hours": [24, 48],
                "local_free_shipping_min": 100,
                "local_cities_ibge": ["3552205"],
                "local_delivery_fee": 10,
                "pickup_enabled": False,
            }
        ],
    )

    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(10), nullable=False, server_default="pf"),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("legal_name", sa.String(200)),
        sa.Column("document", sa.String(20)),
        sa.Column("email", sa.String(200)),
        sa.Column("whatsapp", sa.String(32)),
        sa.Column("whatsapp_opt_in", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("marketing_opt_in", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source", sa.String(30)),
        sa.Column("segment", sa.String(40)),
        sa.Column("notes", sa.Text()),
        *_ts(),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("external_id", sa.String(80)),
        sa.Column("customer_id", sa.Integer()),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("subtotal", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("shipping", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("discount", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("shipping_address", JSONB),
        sa.Column("local_delivery", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("promised_date", sa.Date()),
        sa.Column("sample_rounds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text()),
        *_ts(),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["customers.id"], name=op.f("fk_orders_customer_id_customers")
        ),
        sa.UniqueConstraint("number", name=op.f("uq_orders_number")),
    )
    op.create_index(op.f("ix_orders_status"), "orders", ["status"])
    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("variant_id", sa.Integer()),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("sku", sa.String(80)),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("personalization", JSONB, nullable=False, server_default="{}"),
        sa.Column("material_ids", JSONB, nullable=False, server_default="[]"),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("needs_sample", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("produced", sa.Integer(), nullable=False, server_default="0"),
        *_ts(),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name=op.f("fk_order_items_order_id_orders")
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"], ["variants.id"], name=op.f("fk_order_items_variant_id_variants")
        ),
    )
    op.create_index(op.f("ix_order_items_order_id"), "order_items", ["order_id"])
    op.create_table(
        "order_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("media_url", sa.Text()),
        sa.Column("actor", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name=op.f("fk_order_events_order_id_orders")
        ),
    )
    op.create_index(op.f("ix_order_events_order_id"), "order_events", ["order_id"])
    op.create_table(
        "print_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_item_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("is_sample", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("printer_id", sa.Integer()),
        sa.Column("material_key", sa.String(80), nullable=False),
        sa.Column("due_date", sa.Date()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("failure_reason", sa.Text()),
        *_ts(),
        sa.ForeignKeyConstraint(
            ["order_item_id"],
            ["order_items.id"],
            name=op.f("fk_print_jobs_order_item_id_order_items"),
        ),
        sa.ForeignKeyConstraint(
            ["printer_id"], ["printers.id"], name=op.f("fk_print_jobs_printer_id_printers")
        ),
    )
    op.create_index(op.f("ix_print_jobs_status"), "print_jobs", ["status"])
    op.create_table(
        "produced_fingerprints",
        sa.Column("fingerprint", sa.String(64), primary_key=True),
        sa.Column("first_order_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("audience", sa.String(20), nullable=False),
        sa.Column("to", sa.String(200)),
        sa.Column("template", sa.String(60), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("order_id", sa.Integer()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text()),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        *_ts(),
    )
    op.create_index(op.f("ix_notifications_status"), "notifications", ["status"])


def downgrade() -> None:
    for table in (
        "notifications",
        "produced_fingerprints",
        "print_jobs",
        "order_events",
        "order_items",
        "orders",
        "customers",
        "ops_config",
    ):
        op.drop_table(table)
