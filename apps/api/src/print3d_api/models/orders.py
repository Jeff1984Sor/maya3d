"""Clientes, pedidos, produção e notificações (spec seções 5.0 e 5.2)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from print3d_api.db.base import Base
from print3d_api.models.mixins import IdMixin, TimestampMixin

OPS_CONFIG_ID = 1


class OpsConfig(TimestampMixin, Base):
    """Regras de operação editáveis no admin (amostra, entrega local, contato do dono)."""

    __tablename__ = "ops_config"
    __table_args__ = (CheckConstraint(f"id = {OPS_CONFIG_ID}", name="singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=OPS_CONFIG_ID)
    sample_threshold: Mapped[int] = mapped_column(Integer)
    free_sample_rounds: Mapped[int] = mapped_column(Integer)
    sample_reminder_hours: Mapped[list[int]] = mapped_column(JSONB, default=list)
    local_free_shipping_min: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    local_cities_ibge: Mapped[list[str]] = mapped_column(JSONB, default=list)
    local_delivery_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    pickup_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_whatsapp: Mapped[str | None] = mapped_column(String(32))
    # Pix manual (até o gateway): chave e nome do recebedor exibidos no checkout
    pix_key: Mapped[str | None] = mapped_column(String(140))
    pix_name: Mapped[str | None] = mapped_column(String(100))
    origin_cep: Mapped[str | None] = mapped_column(String(9))  # de onde saem os envios


class Customer(IdMixin, TimestampMixin, Base):
    __tablename__ = "customers"

    kind: Mapped[str] = mapped_column(String(10), default="pf")  # pf | pj
    name: Mapped[str] = mapped_column(String(160))
    legal_name: Mapped[str | None] = mapped_column(String(200))
    document: Mapped[str | None] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(200))
    whatsapp: Mapped[str | None] = mapped_column(String(32))
    whatsapp_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    marketing_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str | None] = mapped_column(String(30))
    segment: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)


class Order(IdMixin, TimestampMixin, Base):
    __tablename__ = "orders"

    number: Mapped[int] = mapped_column(Integer, unique=True)
    channel: Mapped[str] = mapped_column(String(20))  # site | mercadolivre | shopee | manual
    external_id: Mapped[str | None] = mapped_column(String(80))
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"))
    status: Mapped[str] = mapped_column(String(30), index=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal(0))
    shipping: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal(0))
    discount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal(0))
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal(0))
    shipping_address: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    local_delivery: Mapped[bool] = mapped_column(Boolean, default=False)
    promised_date: Mapped[date | None] = mapped_column(Date)
    sample_rounds: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)
    payment_method: Mapped[str | None] = mapped_column(String(20))  # pix_manual | gateway...
    # Link secreto de acompanhamento ("Meus pedidos" sem login, até existir conta com domínio)
    public_token: Mapped[str | None] = mapped_column(String(40), unique=True)


class OrderItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "order_items"

    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    variant_id: Mapped[int | None] = mapped_column(ForeignKey("variants.id"))
    title: Mapped[str] = mapped_column(String(200))
    sku: Mapped[str | None] = mapped_column(String(80))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    personalization: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    material_ids: Mapped[list[int]] = mapped_column(JSONB, default=list)
    # Impressão digital da combinação (design + parâmetros + material/cor): pula a amostra se
    # a mesma combinação já foi produzida e aprovada antes.
    fingerprint: Mapped[str] = mapped_column(String(64))
    needs_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    produced: Mapped[int] = mapped_column(Integer, default=0)


class OrderEvent(IdMixin, Base):
    """Linha do tempo do pedido (o cliente vê em 'Meus pedidos')."""

    __tablename__ = "order_events"

    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(30))
    note: Mapped[str | None] = mapped_column(Text)
    media_url: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(40))


class PrintJob(IdMixin, TimestampMixin, Base):
    __tablename__ = "print_jobs"

    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), index=True)  # fila|imprimindo|concluido|falhou
    printer_id: Mapped[int | None] = mapped_column(ForeignKey("printers.id"))
    material_key: Mapped[str] = mapped_column(String(80))  # agrupa a fila por material/cor
    due_date: Mapped[date | None] = mapped_column(Date)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)


class ProducedFingerprint(Base):
    __tablename__ = "produced_fingerprints"

    fingerprint: Mapped[str] = mapped_column(String(64), primary_key=True)
    first_order_id: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Notification(IdMixin, TimestampMixin, Base):
    """Caixa de saída. Tudo que seria enviado (WhatsApp, e-mail, push) fica aqui; um job envia
    quando o provedor estiver configurado. Sem provedor: fica 'pendente', nada se perde."""

    __tablename__ = "notifications"

    channel: Mapped[str] = mapped_column(String(20))  # whatsapp | email | push
    audience: Mapped[str] = mapped_column(String(20))  # cliente | dono
    to: Mapped[str | None] = mapped_column(String(200))
    template: Mapped[str] = mapped_column(String(60))
    body: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    order_id: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), index=True)  # pendente|enviado|falhou|ignorado
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # id da mensagem no provedor (wamid): liga a resposta de botão ao pedido
    provider_message_id: Mapped[str | None] = mapped_column(String(120), index=True)


class InboundMessage(IdMixin, TimestampMixin, Base):
    """Mensagem recebida pelo webhook. Id único do provedor = idempotência (a Meta reenvia)."""

    __tablename__ = "inbound_messages"

    provider_message_id: Mapped[str] = mapped_column(String(120), unique=True)
    channel: Mapped[str] = mapped_column(String(20), default="whatsapp")
    sender: Mapped[str] = mapped_column(String(32), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    text: Mapped[str | None] = mapped_column(Text)
    button_id: Mapped[str | None] = mapped_column(String(256))
    context_id: Mapped[str | None] = mapped_column(String(120))
    media_id: Mapped[str | None] = mapped_column(String(120))
    handled_as: Mapped[str | None] = mapped_column(String(40))  # comando_dono | aprovacao | ...
    order_id: Mapped[int | None] = mapped_column(Integer)


class Cart(TimestampMixin, Base):
    """Carrinho do visitante (cookie). Vira pedido no checkout."""

    __tablename__ = "carts"

    token: Mapped[str] = mapped_column(String(40), primary_key=True)
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    cep: Mapped[str | None] = mapped_column(String(9))
