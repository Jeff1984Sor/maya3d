"""WhatsApp: envio da caixa de saída e tratamento do que chega pelo webhook.

- Dono (número em Operação): comandos ("1234 enviado", "fila", "vendas"...), resposta no chat.
- Cliente: botões da amostra (Aprovar / Pedir ajuste) avançam o pedido; o texto seguinte a um
  pedido de ajuste vira a descrição do ajuste; qualquer outra mensagem é repassada ao dono.
"""

import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.models import Customer, InboundMessage, Notification, OpsConfig, Order
from print3d_api.models.orders import OPS_CONFIG_ID
from print3d_api.services import notifications, orders
from print3d_core.orders import CUSTOMER_LABELS, OrderStatus
from print3d_notify import Button, NotifyProvider, OutboundMessage
from print3d_notify import commands as owner_commands
from print3d_notify.meta import InboundMessage as Inbound

log = logging.getLogger("print3d.whatsapp")
S = OrderStatus
MAX_ATTEMPTS = 5
NOT_SALES = (S.CANCELADO.value, S.AGUARDANDO_PAGAMENTO.value)


def same_number(a: str | None, b: str | None) -> bool:
    """Compara telefones ignorando formatação e o 9º dígito (a Meta às vezes omite no Brasil)."""
    if not a or not b:
        return False
    da, db = ("".join(c for c in n if c.isdigit()) for n in (a, b))

    def br(n: str) -> str:
        n = n if n.startswith("55") else "55" + n
        return n[:4] + n[5:] if len(n) == 13 and n[4] == "9" else n

    return da == db or br(da) == br(db)


# --- Envio ----------------------------------------------------------------------------------
async def dispatch_pending(session: AsyncSession, provider: NotifyProvider, limit: int = 20) -> int:
    """Envia pendentes. SKIP LOCKED: vários processos podem rodar isto sem duplicar envio."""
    notes = (
        await session.scalars(
            select(Notification)
            .where(Notification.status == "pendente", Notification.channel == "whatsapp")
            .order_by(Notification.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()
    sent = 0
    for note in notes:
        payload = note.payload or {}
        message = OutboundMessage(
            to=note.to or "",
            body=note.body,
            media_url=payload.get("media_url"),
            buttons=[Button(**b) for b in payload.get("buttons") or []],
        )
        note.attempts += 1
        try:
            note.provider_message_id = await provider.send(message)
        except Exception as exc:  # erro do provedor fica registrado; tenta de novo depois
            note.last_error = str(exc)[:500]
            if note.attempts >= MAX_ATTEMPTS:
                note.status = "falhou"
            log.warning("whatsapp falhou", extra={"notification": note.id, "erro": note.last_error})
        else:
            note.status = "enviado"
            note.sent_at = datetime.now(UTC)
            note.last_error = None
            sent += 1
    await session.commit()
    return sent


# --- Recebimento ----------------------------------------------------------------------------
async def handle_inbound(session: AsyncSession, msg: Inbound) -> str:
    """Registra e trata uma mensagem recebida. Devolve como foi tratada (idempotente)."""
    record = InboundMessage(
        provider_message_id=msg.message_id,
        channel="whatsapp",
        sender=msg.sender,
        kind=msg.kind,
        text=msg.text or None,
        button_id=msg.button_id,
        context_id=msg.context_id,
        media_id=msg.media_id,
    )
    session.add(record)
    try:
        await session.flush()
    except IntegrityError:  # a Meta reenviou: já tratada
        await session.rollback()
        return "duplicada"

    ops = await session.get(OpsConfig, OPS_CONFIG_ID)
    if ops and same_number(msg.sender, ops.owner_whatsapp):
        record.handled_as = "comando_dono"
        reply = await _owner_command(session, msg)
        await _reply(session, ops.owner_whatsapp, reply)
    elif msg.kind == "button" and msg.button_id in ("aprovar", "ajuste"):
        record.handled_as, record.order_id = await _sample_answer(session, msg)
    else:
        record.handled_as, record.order_id = await _customer_message(session, msg)
    await session.commit()
    return record.handled_as or "ignorada"


async def _reply(session: AsyncSession, to: str | None, body: str) -> None:
    await notifications.enqueue(
        session, audience="dono", to=to, template="resposta_comando", body=body
    )


async def _owner_command(session: AsyncSession, msg: Inbound) -> str:
    cmd = owner_commands.parse(msg.text)
    if cmd.kind == "avancar" and cmd.order_number and cmd.status:
        order = await session.scalar(select(Order).where(Order.number == cmd.order_number))
        if order is None:
            return f"Não achei o pedido #{cmd.order_number}."
        try:
            order = await orders.advance(
                session,
                order.id,
                cmd.status,
                note="pelo WhatsApp",
                media_url=None,
                actor="dono:whatsapp",
            )
        except orders.OrderError as exc:
            return f"Pedido #{cmd.order_number}: {exc}"
        return f"Pedido #{order.number}: {CUSTOMER_LABELS[S(order.status)]} ✅"
    if cmd.kind == "fila":
        return await _queue_summary(session)
    if cmd.kind == "vendas":
        return await _sales_summary(session)
    if cmd.kind == "entregas":
        return await _deliveries_summary(session)
    return owner_commands.HELP


async def _queue_summary(session: AsyncSession) -> str:
    groups = await orders.print_queue(session)
    if not groups:
        return "Fila vazia. Nada para imprimir agora."
    lines = [f"Fila de impressão ({sum(g.total_pieces for g in groups)} peças):"]
    for g in groups[:8]:
        lines.append(f"• {' + '.join(g.materials)}: {g.total_pieces} peça(s)")
        for j in g.jobs[:5]:
            sample = " (amostra)" if j["is_sample"] else ""
            lines.append(f"   #{j['order_number']} {j['title']} x{j['quantity']}{sample}")
    return "\n".join(lines)


async def _sales_summary(session: AsyncSession) -> str:
    since = datetime.now(UTC) - timedelta(days=7)
    count, total = (
        await session.execute(
            select(func.count(), func.coalesce(func.sum(Order.total), 0)).where(
                Order.created_at >= since, Order.status.not_in(NOT_SALES)
            )
        )
    ).one()
    waiting = await session.scalar(
        select(func.count()).where(Order.status == S.AGUARDANDO_PAGAMENTO.value)
    )
    return (
        f"Últimos 7 dias: {count} pedido(s), {_brl(Decimal(total))}.\n"
        f"Aguardando Pix: {waiting or 0}."
    )


async def _deliveries_summary(session: AsyncSession) -> str:
    rows = (
        await session.scalars(
            select(Order)
            .where(
                Order.local_delivery.is_(True),
                Order.status.in_([S.EMBALADO.value, S.SAIU_PARA_ENTREGA.value]),
            )
            .order_by(Order.promised_date.asc().nulls_last(), Order.number)
        )
    ).all()
    if not rows:
        return "Nenhuma entrega local pendente."
    lines = ["Entregas locais:"]
    for o in rows:
        addr: dict[str, Any] = o.shipping_address or {}
        where = ", ".join(str(addr[k]) for k in ("street", "number", "district") if addr.get(k))
        when = _date(o.promised_date)
        lines.append(f"• #{o.number} {CUSTOMER_LABELS[S(o.status)]} {when} {where}".rstrip())
    return "\n".join(lines)


async def _order_from_context(session: AsyncSession, context_id: str | None) -> Order | None:
    if not context_id:
        return None
    note = await session.scalar(
        select(Notification).where(Notification.provider_message_id == context_id)
    )
    return await session.get(Order, note.order_id) if note and note.order_id else None


async def _customer_of(session: AsyncSession, order: Order) -> Customer | None:
    return await session.get(Customer, order.customer_id) if order.customer_id else None


async def _sample_answer(session: AsyncSession, msg: Inbound) -> tuple[str, int | None]:
    order = await _order_from_context(session, msg.context_id)
    if order is None:
        return "botao_sem_pedido", None
    customer = await _customer_of(session, order)
    if not customer or not same_number(msg.sender, customer.whatsapp):
        return "botao_de_outro_numero", order.id  # só o dono do pedido aprova
    if order.status != S.AMOSTRA_PRONTA.value:
        return "botao_fora_de_hora", order.id
    approved = msg.button_id == "aprovar"
    await orders.advance(
        session,
        order.id,
        (S.NA_FILA if approved else S.AJUSTE_SOLICITADO).value,
        note="aprovado pelo cliente no WhatsApp" if approved else "ajuste pedido no WhatsApp",
        media_url=None,
        actor=f"cliente:{customer.id}",
    )
    if not approved:
        await notifications.enqueue(
            session,
            audience="cliente",
            to=customer.whatsapp,
            template="pedir_detalhe_ajuste",
            body="Certo! Conta pra gente o que você quer ajustar (pode mandar texto ou foto).",
            order_id=order.id,
        )
    return ("aprovacao" if approved else "ajuste"), order.id


async def _customer_message(session: AsyncSession, msg: Inbound) -> tuple[str, int | None]:
    """Texto/foto/áudio de cliente: vai para o dono com o pedido aberto mais recente."""
    customers = (
        await session.scalars(select(Customer).where(Customer.whatsapp.is_not(None)))
    ).all()
    customer = next((c for c in customers if same_number(msg.sender, c.whatsapp)), None)
    order = None
    if customer:
        order = await session.scalar(
            select(Order)
            .where(
                Order.customer_id == customer.id,
                Order.status.not_in([S.ENTREGUE.value, S.CANCELADO.value]),
            )
            .order_by(Order.id.desc())
            .limit(1)
        )
    who = customer.name if customer else f"+{msg.sender}"
    ref = f" (pedido #{order.number}, {CUSTOMER_LABELS[S(order.status)]})" if order else ""
    content = msg.text or {"audio": "[áudio]", "image": "[foto]"}.get(msg.kind, "[mensagem]")
    adjusting = order is not None and order.status == S.AJUSTE_SOLICITADO.value
    prefix = "Ajuste pedido" if adjusting else "Mensagem"
    await notifications.notify_owner(
        session, "mensagem_cliente", f"{prefix} de {who}{ref}: {content}", order
    )
    return ("detalhe_ajuste" if adjusting else "repassada_ao_dono"), order.id if order else None


def _brl(value: Decimal) -> str:
    return "R$ " + f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _date(d: date | None) -> str:
    return d.strftime("%d/%m") if d else ""
