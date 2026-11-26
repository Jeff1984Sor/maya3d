"""Notas fiscais (NF-e modelo 55) emitidas pela plataforma."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from print3d_api.db.base import Base
from print3d_api.models.mixins import IdMixin, TimestampMixin


class FiscalInvoice(IdMixin, TimestampMixin, Base):
    """Uma tentativa de NF-e. O número fica reservado na linha antes de ir à SEFAZ:
    rejeitada pode ser reenviada com o mesmo número; sem resposta → consultar pela chave."""

    __tablename__ = "fiscal_invoices"
    __table_args__ = (UniqueConstraint("ambiente", "serie", "number", name="uq_nfe_numero"),)

    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    ambiente: Mapped[int] = mapped_column(Integer)  # 1 produção | 2 homologação
    serie: Mapped[int] = mapped_column(Integer)
    number: Mapped[int] = mapped_column(Integer)
    # processando | autorizada | rejeitada | denegada | sem_resposta | cancelada
    status: Mapped[str] = mapped_column(String(20), index=True)
    chave: Mapped[str | None] = mapped_column(String(44), unique=True)
    cstat: Mapped[str | None] = mapped_column(String(4))
    motivo: Mapped[str | None] = mapped_column(Text)
    protocolo: Mapped[str | None] = mapped_column(String(20))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal(0))
    recipient: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)  # destinatário usado
    xml: Mapped[str | None] = mapped_column(Text)  # <NFe> assinada enviada
    proc_xml: Mapped[str | None] = mapped_column(Text)  # <nfeProc> (distribuição)
    cancel_xml: Mapped[str | None] = mapped_column(Text)
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # pós-autorização (não bloqueiam a nota): XML no ML e e-mail com etiqueta
    ml_status: Mapped[str | None] = mapped_column(Text)
    email_status: Mapped[str | None] = mapped_column(Text)
