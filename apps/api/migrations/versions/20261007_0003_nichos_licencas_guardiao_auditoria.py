"""nichos configuráveis, licenças, ajustes do Guardião e audit_log

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = postgresql.JSONB()

# Semente congelada (spec 2.1 a 2.8). Depois disso, nicho é cadastro no admin.
SEED_NICHES = [
    (
        "religioso",
        "Religioso",
        300,
        "Acolhedora e reverente, sem exageros comerciais. Respeito à fé em todo texto.",
    ),
    (
        "automotivo",
        "Automotivo",
        50,
        "Técnica e objetiva: compatibilidade (marca, modelo, anos), material e medidas.",
    ),
    ("celular", "Celular", 25, "Prática e moderna."),
    ("brindes", "Brindes", 25, "Profissional e criativa."),
    (
        "datas-comemorativas",
        "Datas comemorativas",
        100,
        "Afetiva e calorosa, focada em presentear e no prazo de entrega da data.",
    ),
    ("fitness", "Fitness", 60, "Energética e motivadora, sem prometer resultado físico."),
    ("chaveiros", "Chaveiros personalizados", 80, "Leve, divertida e pessoal."),
    ("infantil", "Infantil", 20, "Lúdica e segura: decoração e colecionáveis, nunca brinquedo."),
    ("caixas", "Caixas e embalagens", 60, "Elegante e prática: reutilizável e premium."),
]


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
    niches = op.create_table(
        "niches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(40), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("voice", sa.Text()),
        sa.Column("categories", JSONB, nullable=False, server_default="[]"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
        sa.UniqueConstraint("slug", name=op.f("uq_niches_slug")),
    )
    op.bulk_insert(
        niches,
        [
            {
                "slug": s,
                "name": n,
                "target_count": t,
                "voice": v,
                "categories": [],
                "sort_order": i,
                "active": True,
            }
            for i, (s, n, t, v) in enumerate(SEED_NICHES)
        ],
    )
    op.create_table(
        "licenses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("licensor", sa.String(160), nullable=False),
        sa.Column("covered_terms", JSONB, nullable=False, server_default="[]"),
        sa.Column("categories", JSONB, nullable=False, server_default="[]"),
        sa.Column("channels", JSONB, nullable=False, server_default="[]"),
        sa.Column("territory", sa.String(80)),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=False),
        sa.Column("royalty_pct", sa.Numeric(6, 4)),
        sa.Column("royalty_per_unit", sa.Numeric(10, 2)),
        sa.Column("approval_rules", sa.Text()),
        sa.Column("contract_url", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_timestamps(),
    )
    op.create_table(
        "guardian_term_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("term", sa.String(120), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("rule_code", sa.String(60)),
        sa.Column("reason", sa.Text()),
        *_timestamps(),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("actor", sa.String(40), nullable=False),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity_type", sa.String(40)),
        sa.Column("entity_id", sa.String(60)),
        sa.Column("decision", sa.String(40)),
        sa.Column("reason", sa.Text()),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
    )
    op.create_index(op.f("ix_audit_log_created_at"), "audit_log", ["created_at"])


def downgrade() -> None:
    for table in ("audit_log", "guardian_term_overrides", "licenses", "niches"):
        op.drop_table(table)
