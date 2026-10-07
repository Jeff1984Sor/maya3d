"""whatsapp: id da mensagem no provedor e mensagens recebidas (webhook)

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("provider_message_id", sa.String(120)))
    op.create_index(
        op.f("ix_notifications_provider_message_id"), "notifications", ["provider_message_id"]
    )
    op.create_table(
        "inbound_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider_message_id", sa.String(120), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("sender", sa.String(32), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("text", sa.Text()),
        sa.Column("button_id", sa.String(256)),
        sa.Column("context_id", sa.String(120)),
        sa.Column("media_id", sa.String(120)),
        sa.Column("handled_as", sa.String(40)),
        sa.Column("order_id", sa.Integer()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "provider_message_id", name=op.f("uq_inbound_messages_provider_message_id")
        ),
    )
    op.create_index(op.f("ix_inbound_messages_sender"), "inbound_messages", ["sender"])


def downgrade() -> None:
    op.drop_index(op.f("ix_inbound_messages_sender"), table_name="inbound_messages")
    op.drop_table("inbound_messages")
    op.drop_index(op.f("ix_notifications_provider_message_id"), table_name="notifications")
    op.drop_column("notifications", "provider_message_id")
