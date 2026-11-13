"""Gateway de pagamento (Mercado Pago): Pix automático na loja.

- No checkout: cobrança Pix (QR + copia e cola). Sem gateway ou com falha: Pix manual (chave).
- Confirmação: aviso assinado do Mercado Pago (com domínio) e, sempre, consulta periódica dos
  pendentes — funciona mesmo sem domínio. Aprovado = pedido "pago" e produção começa sozinha.
- O valor aprovado é conferido com o total do pedido antes de liberar.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from print3d_api.models import ChannelFeeBand, Customer, Order, Payment
from print3d_api.schemas.store import CardPaymentOut
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


async def card_public_key(session: AsyncSession) -> str | None:
    """Public Key do Mercado Pago (vai para o navegador) se o cartão estiver disponível."""
    s = await _settings(session)
    ok = (
        s["MP_ACCESS_TOKEN"]
        and s["MP_PUBLIC_KEY"]
        and (s["PUBLIC_API_URL"] or "").startswith("https://")
    )
    return s["MP_PUBLIC_KEY"] if ok else None


# mensagens para o cliente (status_detail do Mercado Pago); o resto cai na genérica
_CARD_MESSAGES = {
    "cc_rejected_insufficient_amount": "Saldo ou limite insuficiente. Tente outro cartão ou o Pix.",
    "cc_rejected_bad_filled_security_code": "Código de segurança incorreto. Confira e tente.",
    "cc_rejected_bad_filled_date": "Data de validade incorreta. Confira e tente de novo.",
    "cc_rejected_bad_filled_card_number": "Número do cartão incorreto. Confira e tente de novo.",
    "cc_rejected_bad_filled_other": "Algum dado do cartão está incorreto. Confira e tente de novo.",
    "cc_rejected_call_for_authorize": "O banco pediu autorização: ligue para ele e tente de novo.",
    "cc_rejected_card_disabled": "Cartão bloqueado para compras online. Fale com o banco.",
    "cc_rejected_duplicated_payment": "Pagamento repetido. Confira o extrato antes de tentar.",
    "cc_rejected_high_risk": "Pagamento recusado por segurança. Use outro cartão ou o Pix.",
    "cc_rejected_max_attempts": "Muitas tentativas. Use outro cartão ou o Pix.",
}


async def pay_card(
    session: AsyncSession, order: Order, customer: Customer | None, data: Any
) -> CardPaymentOut:
    """Cobra o cartão (token do formulário seguro) pelo TOTAL DO PEDIDO calculado aqui."""
    mp = await gateway(session)
    if mp is None:
        raise MercadoPagoError("cartão indisponível no momento")
    s = await _settings(session)
    base = s["PUBLIC_API_URL"] or ""
    notify = f"{base.rstrip('/')}/v1/webhooks/mercadopago" if base.startswith("https://") else None
    email = (customer.email if customer else None) or (data.payer.email if data.payer else None)
    ident = data.payer.identification if data.payer else None
    state = await mp.create_card(
        amount=order.total,
        token=data.token,
        installments=data.installments,
        payment_method_id=data.payment_method_id,
        issuer_id=data.issuer_id,
        payer_email=email or "cliente@sem-email.invalid",
        identification={"type": ident.type, "number": ident.number} if ident else None,
        description=f"Pedido #{order.number}",
        reference=f"pedido-{order.id}",
        idempotency_key=f"pedido-{order.id}-cartao-{data.token[-24:]}",
        notification_url=notify,
    )
    payment = Payment(
        order_id=order.id,
        provider=PROVIDER,
        method="cartao",
        external_id=state.payment_id,
        status="pending",
        amount=order.total,
    )
    session.add(payment)
    await session.flush()
    paid = await apply_state(session, payment, state)
    if paid:
        message = "Pagamento aprovado! Seu pedido já foi para a produção."
    elif state.status in ("in_process", "pending", "authorized"):
        message = "Pagamento em análise pelo banco. Avisamos assim que for aprovado."
    else:
        message = _CARD_MESSAGES.get(
            state.status_detail, "O cartão foi recusado. Tente outro cartão ou pague com Pix."
        )
    return CardPaymentOut(status=state.status, paid=paid, message=message)


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
    await learn_fee(session, payment, state)
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
            note=f"{'Cartão' if payment.method == 'cartao' else 'Pix'} aprovado pelo Mercado Pago",
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
                Payment.status.in_(("pending", "in_process", "authorized")),
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


async def learn_fee(session: AsyncSession, payment: Payment, state: PaymentState) -> None:
    """A taxa real do Pix vem de cada pagamento aprovado: atualiza a tarifa "site_pix" usada
    no preço da loja (fonte "api"). Taxa cadastrada à mão pelo dono não é sobrescrita."""
    if state.amount <= 0 or payment.method != "pix":
        return
    rate = (state.fee / state.amount).quantize(Decimal("0.0001"))
    band = await session.scalar(
        select(ChannelFeeBand).where(
            ChannelFeeBand.channel == "site_pix", ChannelFeeBand.category.is_(None)
        )
    )
    if band is None:
        session.add(
            ChannelFeeBand(
                channel="site_pix",
                commission_rate=rate,
                source="api",
                notes=f"taxa real do Mercado Pago (pagamento {payment.external_id})",
            )
        )
    elif band.source == "api" and band.commission_rate != rate:
        band.commission_rate = rate
        band.notes = f"taxa real do Mercado Pago (pagamento {payment.external_id})"
