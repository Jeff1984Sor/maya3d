"""Caixa de saída de notificações. Quem gera mensagem só enfileira aqui; o worker envia quando
houver provedor (Meta WhatsApp Cloud API, e-mail). Sem provedor, fica pendente — nada se perde.

Regras da spec: pedido de Mercado Livre/Shopee NUNCA gera contato fora da plataforma;
mensagem para cliente só com opt-in de WhatsApp.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.models import BrandSettings, Customer, Notification, OpsConfig, Order
from print3d_api.models.brand import SINGLETON_ID
from print3d_api.models.orders import OPS_CONFIG_ID
from print3d_core.orders import CUSTOMER_LABELS, OrderStatus

MARKETPLACES = frozenset({"mercadolivre", "shopee"})


async def _brand_name(session: AsyncSession) -> str:
    brand = await session.get(BrandSettings, SINGLETON_ID)
    return brand.name if brand else "nossa loja"


async def enqueue(
    session: AsyncSession,
    *,
    audience: str,
    to: str | None,
    template: str,
    body: str,
    order_id: int | None = None,
    payload: dict[str, Any] | None = None,
    channel: str = "whatsapp",
) -> Notification:
    note = Notification(
        channel=channel,
        audience=audience,
        to=to,
        template=template,
        body=body,
        payload=payload or {},
        order_id=order_id,
        status="pendente" if to else "ignorado",
        last_error=None if to else "sem destinatário/opt-in",
    )
    session.add(note)
    await session.flush()
    return note


async def notify_owner(
    session: AsyncSession, template: str, body: str, order: Order | None = None
) -> Notification:
    ops = await session.get(OpsConfig, OPS_CONFIG_ID)
    return await enqueue(
        session,
        audience="dono",
        to=ops.owner_whatsapp if ops else None,
        template=template,
        body=body,
        order_id=order.id if order else None,
    )


async def notify_customer_status(
    session: AsyncSession,
    order: Order,
    status: OrderStatus,
    *,
    media_url: str | None = None,
    buttons: list[dict[str, str]] | None = None,
) -> Notification | None:
    """Aviso de status ao cliente (site/app). Marketplace: proibido sair da plataforma."""
    if order.channel in MARKETPLACES:
        return None
    customer = await session.get(Customer, order.customer_id) if order.customer_id else None
    to = customer.whatsapp if customer and customer.whatsapp_opt_in else None
    loja = await _brand_name(session)
    nome = customer.name.split()[0] if customer else ""
    saudacao = f"Olá, {nome}!" if nome else "Olá!"
    body = f"{saudacao} Pedido #{order.number} na {loja}: {CUSTOMER_LABELS[status]}."
    return await enqueue(
        session,
        audience="cliente",
        to=to,
        template=f"pedido_{status.value}",
        body=body,
        order_id=order.id,
        payload={"media_url": media_url, "buttons": buttons or []},
    )
