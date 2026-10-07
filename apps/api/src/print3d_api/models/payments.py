from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from print3d_api.db.base import Base
from print3d_api.models.mixins import IdMixin, TimestampMixin


class Payment(IdMixin, TimestampMixin, Base):
    """Cobrança no gateway (Mercado Pago). Aprovada = pedido vai sozinho para produção."""

    __tablename__ = "payments"

    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(20))  # mercadopago
    method: Mapped[str] = mapped_column(String(20))  # pix | cartao
    external_id: Mapped[str] = mapped_column(String(40), unique=True)
    # pending | approved | rejected | cancelled | expired | refunded
    status: Mapped[str] = mapped_column(String(20), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    qr_code: Mapped[str | None] = mapped_column(Text)
    qr_code_base64: Mapped[str | None] = mapped_column(Text)
    ticket_url: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
