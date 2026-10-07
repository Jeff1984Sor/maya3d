"""materiais, impressoras, embalagens, custos, tarifas por canal e catálogo

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB()


def _timestamps() -> list[sa.Column[object]]:
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
        "materials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("color_name", sa.String(60), nullable=False),
        sa.Column("color_hex", sa.String(7), nullable=False),
        sa.Column("brand", sa.String(80)),
        sa.Column("finish", sa.String(40)),
        sa.Column("supplier", sa.String(120)),
        sa.Column("price_per_kg", sa.Numeric(10, 2), nullable=False),
        sa.Column("stock_grams", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reorder_point_grams", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
    )
    op.create_table(
        "printers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("bed_x_mm", sa.Integer(), nullable=False),
        sa.Column("bed_y_mm", sa.Integer(), nullable=False),
        sa.Column("bed_z_mm", sa.Integer(), nullable=False),
        sa.Column("avg_watts", sa.Integer(), nullable=False),
        sa.Column("hourly_wear", sa.Numeric(10, 2), nullable=False),
        sa.Column("enclosed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("has_ams", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("supported_materials", JSONB, nullable=False, server_default="[]"),
        sa.Column("status", sa.String(20), nullable=False, server_default="ativa"),
        *_timestamps(),
    )
    op.create_table(
        "packaging_boxes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("inner_x_mm", sa.Integer(), nullable=False),
        sa.Column("inner_y_mm", sa.Integer(), nullable=False),
        sa.Column("inner_z_mm", sa.Integer(), nullable=False),
        sa.Column("weight_g", sa.Integer(), nullable=False),
        sa.Column("cost", sa.Numeric(10, 2), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
    )
    cost_config = op.create_table(
        "cost_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("energy_price_kwh", sa.Numeric(8, 4), nullable=False),
        sa.Column("labor_per_hour", sa.Numeric(10, 2), nullable=False),
        sa.Column("failure_rate", sa.Numeric(5, 4), nullable=False),
        sa.Column("min_profit", sa.Numeric(10, 2), nullable=False),
        sa.Column("default_margin", sa.Numeric(5, 4), nullable=False),
        sa.Column("margin_by_category", JSONB, nullable=False, server_default="{}"),
        *_timestamps(),
        sa.CheckConstraint("id = 1", name=op.f("ck_cost_config_singleton")),
    )
    # Valores iniciais CONSERVADORES para o sistema funcionar; o dono ajusta no admin.
    op.bulk_insert(
        cost_config,
        [
            {
                "id": 1,
                "energy_price_kwh": 0.95,
                "labor_per_hour": 30,
                "failure_rate": 0.10,
                "min_profit": 8,
                "default_margin": 0.40,
                "margin_by_category": {},
            }
        ],
    )
    op.create_table(
        "channel_fee_bands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel", sa.String(40), nullable=False),
        sa.Column("category", sa.String(120)),
        sa.Column("min_price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("max_price", sa.Numeric(10, 2)),
        sa.Column("commission_rate", sa.Numeric(6, 4), nullable=False),
        sa.Column("fixed_fee", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("notes", sa.Text()),
        *_timestamps(),
    )
    op.create_index(op.f("ix_channel_fee_bands_channel"), "channel_fee_bands", ["channel"])

    op.create_table(
        "designs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("origin", sa.String(30), nullable=False),
        sa.Column("author", sa.String(160)),
        sa.Column("license", sa.String(80), nullable=False),
        sa.Column("source_url", sa.Text()),
        sa.Column("attribution_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("attribution_text", sa.Text()),
        sa.Column("source_file_url", sa.Text()),
        sa.Column("params_schema", JSONB, nullable=False, server_default="{}"),
        sa.Column("ip_status", sa.String(20), nullable=False, server_default="pendente"),
        sa.Column("ip_reason", sa.Text()),
        sa.Column("printability_notes", sa.Text()),
        *_timestamps(),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("design_id", sa.Integer(), nullable=False),
        sa.Column("niche", sa.String(40), nullable=False),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("subcategory", sa.String(120)),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(220), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("tags", JSONB, nullable=False, server_default="[]"),
        sa.Column("occasions", JSONB, nullable=False, server_default="[]"),
        sa.Column("age_rating", sa.String(20)),
        sa.Column("min_material", sa.String(20)),
        sa.Column("customizable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(20), nullable=False, server_default="rascunho"),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["design_id"], ["designs.id"], name=op.f("fk_products_design_id_designs")
        ),
        sa.UniqueConstraint("slug", name=op.f("uq_products_slug")),
    )
    op.create_index(op.f("ix_products_design_id"), "products", ["design_id"])
    op.create_table(
        "variants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(80), nullable=False),
        sa.Column("size_label", sa.String(40)),
        sa.Column("finish", sa.String(20), nullable=False, server_default="cor_unica"),
        sa.Column("params", JSONB, nullable=False, server_default="{}"),
        sa.Column("color_by_part", JSONB, nullable=False, server_default="{}"),
        sa.Column("dims_mm", JSONB),
        sa.Column("grams_by_material", JSONB),
        sa.Column("print_seconds", sa.Integer()),
        sa.Column("slicing_source", sa.String(20), nullable=False, server_default="a_confirmar"),
        sa.Column("post_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("packaging_id", sa.Integer()),
        sa.Column("packed_weight_g", sa.Integer()),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], name=op.f("fk_variants_product_id_products")
        ),
        sa.ForeignKeyConstraint(
            ["packaging_id"],
            ["packaging_boxes.id"],
            name=op.f("fk_variants_packaging_id_packaging_boxes"),
        ),
        sa.UniqueConstraint("sku", name=op.f("uq_variants_sku")),
    )
    op.create_index(op.f("ix_variants_product_id"), "variants", ["product_id"])


def downgrade() -> None:
    for table in (
        "variants",
        "products",
        "designs",
        "channel_fee_bands",
        "cost_config",
        "packaging_boxes",
        "printers",
        "materials",
    ):
        op.drop_table(table)
