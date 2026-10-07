"""Gateway de pagamento (Mercado Pago): Pix automático na loja.

- No checkout: cobrança Pix (QR + copia e cola). Sem gateway ou com falha: Pix manual (chave).
- Confirmação: aviso assinado do Mercado Pago (com domínio) e, sempre, consulta periódica dos
  pendentes — funciona mesmo sem domínio. Aprovado = pedido "pago" e produção começa sozinha.
- O valor aprovado é conferido com o total do pedido antes de liberar.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from print3d_api.models import Customer, Order, Payment
from print3d_api.services import audit, integrations, notifications, orders
from print3d_channels.mercadopago import MercadoPago, MercadoPagoError, PaymentState
from print3d_core.orders import OrderStatus

log = logging.getLogger("print3d.payments")
PROVIDER = "mercadopago"
POLL_WINDOW = timedelta(hours=26)  # Pix vence em 24 h; consulta um pouco além


async def _settings(session: AsyncSession) -> dict[str, str | None]:
    values = await integrations.load(session)
    keys = ("MP_ACCESS_TOKEN", "MP_PUBLIC_KEY", "MP_WEBHOOK_SECRET", "PUBLIC_API_URL")
    return {k: values.get(k) or integrations.env_value(k) for k in keys}


async def gateway(session: AsyncSession) -> MercadoPago | None:
    token = (await _settings(session))["MP_ACCESS_TOKEN"]
    return MercadoPago(token) if token else None


async def status(session: AsyncSession) -> dict[str, Any]:
    s = await _settings(session)
    token = s["MP_ACCESS_TOKEN"] or ""
    return {
        "configured": bool(token),
        "mode": "teste" if token.startswith("TEST-") else ("produção" if token else None),
        "webhook_ready": bool(
            s["MP_WEBHOOK_SECRET"]
            and s["PUBLIC_API_URL"]
            and s["PUBLIC_API_URL"].startswith("https://")
        ),
        "card_ready": bool(s["MP_PUBLIC_KEY"] and s["PUBLIC_API_URL"]),
        "webhook_path": "/v1/webhooks/mercadopago",
    }


async def charge_pix(session: AsyncSession, order: Order, customer: Customer) -> Payment | None:
    """Cria a cobrança Pix do pedido. None = sem gateway (fica o Pix manual)."""
    mp = await gateway(session)
    if mp is None:
        return None
    s = await _settings(session)
    base = s["PUBLIC_API_URL"]
    notify = (
        f"{base.rstrip('/')}/v1/webhooks/mercadopago"
        if base and base.startswith("https://")
        else None
    )
    charge = await mp.create_pix(
        amount=order.total,
        description=f"Pedido #{order.number}",
        payer_email=customer.email or "cliente@sem-email.invalid",
        payer_name=customer.name,
        reference=f"pedido-{order.id}",
        idempotency_key=f"pedido-{order.id}-pix",
        notification_url=notify,
    )
    payment = Payment(
        order_id=order.id,
        provider=PROVIDER,
        method="pix",
        external_id=charge.payment_id,
        status=charge.status,
        amount=order.total,
        qr_code=charge.qr_code,
        qr_code_base64=charge.qr_code_base64,
        ticket_url=charge.ticket_url,
        expires_at=charge.expires_at,
    )
    session.add(payment)
    order.payment_method = "pix_mercadopago"
    return payment


async def current_pix(session: AsyncSession, order_id: int) -> Payment | None:
    return await session.scalar(
        select(Payment)
        .where(Payment.order_id == order_id, Payment.method == "pix", Payment.status == "pending")
        .order_by(Payment.id.desc())
    )


async def apply_state(session: AsyncSession, payment: Payment, state: PaymentState) -> bool:
    """Atualiza o pagamento; se aprovado e o valor bate, o pedido vira "pago". True = pagou."""
    previous = payment.status
    payment.status = state.status
    payment.raw = {"status": state.status, "amount": str(state.amount)}
    if not state.paid or previous == "approved":
        await session.commit()
        return False
    order = await session.get(Order, payment.order_id)
    if order is None:
        await session.commit()
        return False
    if state.amount < order.total:
        payment.status = "divergente"
        await notifications.notify_owner(
            session,
            "pagamento_divergente",
            f"Pedido #{order.number}: Mercado Pago aprovou R$ {state.amount}, mas o total é "
            f"R$ {order.total}. Confira antes de produzir.",
            order,
        )
        await session.commit()
        return False
    payment.paid_at = datetime.now(UTC)
    await audit.record(
        session,
        actor="mercadopago",
        action="pagamento_aprovado",
        entity_type="order",
        entity_id=order.id,
        payload={"pagamento": payment.external_id, "valor": str(state.amount)},
    )
    await session.commit()
    if order.status == OrderStatus.AGUARDANDO_PAGAMENTO.value:
        await orders.advance(
            session,
            order.id,
            OrderStatus.PAGO.value,
            note="Pix aprovado pelo Mercado Pago",
            media_url=None,
            actor="mercadopago",
        )
    return True


async def check(session: AsyncSession, external_id: str) -> bool:
    payment = await session.scalar(select(Payment).where(Payment.external_id == external_id))
    mp = await gateway(session)
    if payment is None or mp is None:
        return False
    return await apply_state(session, payment, await mp.payment(external_id))


async def poll_pending(session: AsyncSession) -> int:
    """Consulta os Pix pendentes recentes. Devolve quantos foram aprovados agora."""
    since = datetime.now(UTC) - POLL_WINDOW
    pending = (
        await session.scalars(
            select(Payment.external_id).where(
                Payment.provider == PROVIDER,
                Payment.status == "pending",
                Payment.created_at >= since,
            )
        )
    ).all()
    paid = 0
    for external_id in pending:
        try:
            paid += await check(session, external_id)
        except MercadoPagoError as exc:
            log.warning(
                "consulta de pagamento falhou", extra={"pagamento": external_id, "erro": str(exc)}
            )
    return paid


async def run_poller(factory: async_sessionmaker[AsyncSession], interval: float = 120.0) -> None:
    """Confirmação automática sem domínio: consulta os pendentes a cada 2 minutos."""
    while True:
        try:
            async with factory() as session:
                if await gateway(session) is not None:
                    done = await poll_pending(session)
                    if done:
                        log.info("Pix confirmados", extra={"n": done})
        except Exception:
            log.exception("falha na consulta de pagamentos")
        await asyncio.sleep(interval)


async def webhook_secret(session: AsyncSession) -> str | None:
    return (await _settings(session))["MP_WEBHOOK_SECRET"]
