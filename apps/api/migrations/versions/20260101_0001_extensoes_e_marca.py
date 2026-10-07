"""extensões do Postgres e brand_settings (com linha semente neutra)

Revision ID: 0001
Revises:
Create Date: 2026-01-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Paleta da seção 5.1 da especificação. Nome neutro: o dono troca no admin.
SEED_COLORS = {
    "light": {
        "bg": "#F7F4EF", "surface": "#FFFFFF", "ink": "#1E1E24", "muted": "#6B7280",
        "primary": "#FF6B2C", "secondary": "#14B8A6", "border": "#E7E2DA",
    },
    "dark": {
        "bg": "#141418", "surface": "#1E1E24", "ink": "#F7F4EF", "muted": "#9CA3AF",
        "primary": "#FF6B2C", "secondary": "#14B8A6", "border": "#2E2E36",
    },
}
SEED_FONTS = {"heading": "Space Grotesk", "body": "Inter"}


def upgrade() -> None:
    # vector: busca semântica | pg_trgm/unaccent: Guardião (normalização) e busca textual
    for ext in ("vector", "pg_trgm", "unaccent"):
        op.execute(f"CREATE EXTENSION IF NOT EXISTS {ext}")

    brand = op.create_table(
        "brand_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("tagline", sa.String(240)),
        sa.Column("logo_light_url", sa.Text()),
        sa.Column("logo_dark_url", sa.Text()),
        sa.Column("favicon_url", sa.Text()),
        sa.Column("colors", postgresql.JSONB(), nullable=False),
        sa.Column("fonts", postgresql.JSONB(), nullable=False),
        sa.Column("domain", sa.String(255)),
        sa.Column("contact_email", sa.String(255)),
        sa.Column("contact_whatsapp", sa.String(32)),
        sa.Column("social", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("cnpj", sa.String(18)),
        sa.Column("legal_name", sa.String(255)),
        sa.Column("voice", sa.Text()),
        sa.Column("voice_by_niche", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("id = 1", name=op.f("ck_brand_settings_singleton")),
    )
    op.bulk_insert(
        brand,
        [
            {
                "id": 1,
                "name": "Print3D",
                "tagline": "Peças impressas em 3D, feitas para você",
                "colors": SEED_COLORS,
                "fonts": SEED_FONTS,
                "social": {},
                "voice_by_niche": {},
            }
        ],
    )


def downgrade() -> None:
    op.drop_table("brand_settings")
    # Extensões ficam: outras migrações/ambientes podem depender delas.
