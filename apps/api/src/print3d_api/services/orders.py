"""Pedidos e produção (spec 5.0): criação com regra de amostra, avanço de status com
notificações, fila de impressão agrupada por material/cor e impressão digital de combinações."""

import secrets
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.models import (
    Customer,
    Material,
    OpsConfig,
    Order,
    OrderEvent,
    OrderItem,
    PrintJob,
    ProducedFingerprint,
    Product,
    Variant,
)
from print3d_api.models.orders import OPS_CONFIG_ID
from print3d_api.schemas.orders import (
    CustomerOut,
    OrderCreate,
    OrderDetail,
    OrderEventOut,
    OrderItemOut,
    OrderSummary,
    PrintJobOut,
    QueueGroup,
)
from print3d_api.services import audit, notifications
from print3d_core.orders import (
    NEXT_STEP,
    TRANSITIONS,
    OrderStatus,
    TransitionError,
    check_transition,
    fingerprint,
    material_key,
    needs_sample,
)

S = OrderStatus
OPEN_JOBS = ("fila", "imprimindo")
APPROVE_BUTTONS = [{"id": "aprovar", "title": "Aprovar"}, {"id": "ajuste", "title": "Pedir ajuste"}]


class OrderError(Exception):
    def __init__(self, message: str, *, not_found: bool = False) -> None:
        super().__init__(message)
        self.not_found = not_found


def _now() -> datetime:
    return datetime.now(UTC)


async def _ops(session: AsyncSession) -> OpsConfig:
    ops = await session.get(OpsConfig, OPS_CONFIG_ID)
    if ops is None:
        raise OrderError("ops_config ausente (rode as migrações)")
    return ops


async def _event(
    session: AsyncSession,
    order: Order,
    status: str,
    actor: str,
    note: str | None = None,
    media_url: str | None = None,
) -> None:
    session.add(
        OrderEvent(order_id=order.id, status=status, actor=actor, note=note, media_url=media_url)
    )
    await session.flush()


async def _items(session: AsyncSession, order_id: int) -> Sequence[OrderItem]:
    stmt = select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.id)
    return (await session.scalars(stmt)).all()


def _job(item: OrderItem, quantity: int, order: Order, *, sample: bool) -> PrintJob:
    return PrintJob(
        order_item_id=item.id,
        quantity=quantity,
        is_sample=sample,
        status="fila",
        material_key=material_key(item.material_ids),
        due_date=order.promised_date,
    )


async def _remember(session: AsyncSession, items: Sequence[OrderItem], order: Order) -> None:
    """Grava a impressão digital: da próxima vez, a mesma combinação pula a amostra."""
    for item in items:
        if await session.get(ProducedFingerprint, item.fingerprint) is None:
            session.add(ProducedFingerprint(fingerprint=item.fingerprint, first_order_id=order.id))
    await session.flush()


async def _start_production(
    session: AsyncSession, order: Order, items: Sequence[OrderItem], ops: OpsConfig
) -> None:
    """Pago → fila (ou amostra). Só aqui nascem as impressões e o aviso de venda ao dono."""
    for item in items:
        session.add(
            _job(item, 1 if item.needs_sample else item.quantity, order, sample=item.needs_sample)
        )
    with_sample = any(i.needs_sample for i in items)
    order.status = (S.IMPRIMINDO_AMOSTRA if with_sample else S.NA_FILA).value
    note = (
        f"amostra exigida: item acima de {ops.sample_threshold} unidades nunca produzido antes"
        if with_sample
        else None
    )
    await _event(session, order, order.status, "sistema", note)
    resumo = "; ".join(f"{i.quantity}x {i.title}" for i in items)
    await notifications.notify_owner(
        session,
        "nova_venda",
        f"Nova venda #{order.number} ({order.channel}): {resumo}. Total R$ {order.total}.",
        order,
    )
    await notifications.notify_customer_status(session, order, S(order.status))


async def create_order(
    session: AsyncSession,
    data: OrderCreate,
    *,
    awaiting_payment: bool = False,
    payment_method: str | None = None,
) -> Order:
    """Venda registrada. Loja (Pix manual/gateway) nasce aguardando pagamento e só entra em
    produção quando o pagamento é confirmado."""
    ops = await _ops(session)
    if data.customer_id and await session.get(Customer, data.customer_id) is None:
        raise OrderError(f"cliente {data.customer_id} não existe", not_found=True)

    last = await session.scalar(select(func.max(Order.number)))
    subtotal = sum((i.unit_price * i.quantity for i in data.items), Decimal(0))
    order = Order(
        number=(last or 1000) + 1,
        channel=data.channel,
        external_id=data.external_id,
        customer_id=data.customer_id,
        status=(S.AGUARDANDO_PAGAMENTO if awaiting_payment else S.PAGO).value,
        subtotal=subtotal,
        shipping=data.shipping,
        discount=data.discount,
        total=subtotal + data.shipping - data.discount,
        shipping_address=data.shipping_address,
        local_delivery=data.local_delivery,
        promised_date=data.promised_date,
        notes=data.notes,
        sample_rounds=0,
        payment_method=payment_method,
        public_token=secrets.token_urlsafe(18),
    )
    session.add(order)
    await session.flush()
    await _event(session, order, order.status, "sistema", f"venda via {data.channel}")

    items: list[OrderItem] = []
    for line in data.items:
        title, sku = line.title, None
        if line.variant_id is not None:
            variant = await session.get(Variant, line.variant_id)
            if variant is None:
                raise OrderError(f"variante {line.variant_id} não existe", not_found=True)
            product = await session.get(Product, variant.product_id)
            sku = variant.sku
            title = title or (
                f"{product.title} {variant.size_label or ''}".strip() if product else sku
            )
        fp = fingerprint(line.variant_id, line.personalization, line.material_ids)
        produced_before = await session.get(ProducedFingerprint, fp) is not None
        item = OrderItem(
            order_id=order.id,
            variant_id=line.variant_id,
            title=title or "Item",
            sku=sku,
            quantity=line.quantity,
            unit_price=line.unit_price,
            personalization=line.personalization,
            material_ids=line.material_ids,
            fingerprint=fp,
            needs_sample=needs_sample(line.quantity, ops.sample_threshold, produced_before),
            produced=0,
        )
        session.add(item)
        items.append(item)
    await session.flush()

    if awaiting_payment:
        await notifications.notify_customer_status(session, order, S.AGUARDANDO_PAGAMENTO)
    else:
        await _start_production(session, order, items, ops)
    await audit.record(
        session,
        actor="sistema",
        action="pedido_criado",
        entity_type="order",
        entity_id=order.id,
        decision=order.status,
        payload={
            "canal": order.channel,
            "total": str(order.total),
            "amostra": any(i.needs_sample for i in items),
        },
    )
    await session.commit()
    await session.refresh(order)
    return order


async def advance(
    session: AsyncSession,
    order_id: int,
    target: str,
    *,
    note: str | None,
    media_url: str | None,
    actor: str,
) -> Order:
    order = await session.get(Order, order_id)
    if order is None:
        raise OrderError(f"pedido {order_id} não existe", not_found=True)
    try:
        new = check_transition(order.status, target)
    except TransitionError as exc:
        raise OrderError(str(exc)) from exc
    previous = S(order.status)
    items = await _items(session, order.id)
    ops = await _ops(session)

    if new is S.PAGO and previous is S.AGUARDANDO_PAGAMENTO:
        order.status = S.PAGO.value
        await _event(session, order, S.PAGO.value, actor, note or "pagamento confirmado")
        await _start_production(session, order, items, ops)
        await audit.record(
            session,
            actor=actor,
            action="pagamento_confirmado",
            entity_type="order",
            entity_id=order.id,
            decision=order.status,
            reason=note,
        )
        await session.commit()
        await session.refresh(order)
        return order
    if new is S.NA_FILA and previous is S.AMOSTRA_PRONTA:
        # aprovado: o restante entra na fila e a combinação fica conhecida
        for item in items:
            if item.needs_sample and item.quantity > 1:
                session.add(_job(item, item.quantity - 1, order, sample=False))
        await _remember(session, [i for i in items if i.needs_sample], order)
        await notifications.notify_owner(
            session, "amostra_aprovada", f"Amostra do pedido #{order.number} aprovada.", order
        )
    elif new is S.AJUSTE_SOLICITADO:
        order.sample_rounds += 1
        fee = order.sample_rounds > ops.free_sample_rounds
        await notifications.notify_owner(
            session,
            "ajuste_solicitado",
            f"Pedido #{order.number}: ajuste na amostra (rodada {order.sample_rounds})"
            + (" — acima das rodadas grátis, cobrar taxa de amostra." if fee else ".")
            + (f" Pedido: {note}" if note else ""),
            order,
        )
    elif new is S.IMPRIMINDO_AMOSTRA and previous is S.AJUSTE_SOLICITADO:
        for item in items:
            if item.needs_sample:
                session.add(_job(item, 1, order, sample=True))
    elif new is S.ENTREGUE:
        await _remember(session, items, order)
    elif new is S.CANCELADO:
        jobs = (
            await session.scalars(
                select(PrintJob).where(
                    PrintJob.order_item_id.in_([i.id for i in items]),
                    PrintJob.status == "fila",
                )
            )
        ).all()
        for job in jobs:
            job.status = "cancelado"

    order.status = new.value
    await _event(session, order, new.value, actor, note, media_url)
    await notifications.notify_customer_status(
        session,
        order,
        new,
        media_url=media_url,
        buttons=APPROVE_BUTTONS if new is S.AMOSTRA_PRONTA else None,
    )
    await audit.record(
        session,
        actor=actor,
        action="status_pedido",
        entity_type="order",
        entity_id=order.id,
        decision=new.value,
        reason=note,
    )
    await session.commit()
    await session.refresh(order)
    return order


async def job_action(
    session: AsyncSession,
    job_id: int,
    action: str,
    *,
    reason: str | None = None,
    printer_id: int | None = None,
) -> PrintJob:
    job = await session.get(PrintJob, job_id)
    if job is None:
        raise OrderError(f"impressão {job_id} não existe", not_found=True)
    item = await session.get(OrderItem, job.order_item_id)
    order = await session.get(Order, item.order_id) if item else None
    if item is None or order is None:
        raise OrderError("impressão sem pedido")

    if action == "iniciar":
        if job.status != "fila":
            raise OrderError("só inicia impressão que está na fila")
        job.status, job.started_at, job.printer_id = "imprimindo", _now(), printer_id
        if order.status == S.NA_FILA.value:
            await advance_internal(session, order, S.IMPRIMINDO)
    elif action == "concluir":
        if job.status not in OPEN_JOBS:
            raise OrderError("impressão já encerrada")
        job.status, job.finished_at = "concluido", _now()
        item.produced = min(item.quantity, item.produced + job.quantity)
    elif action == "falhou":
        if job.status not in OPEN_JOBS:
            raise OrderError("impressão já encerrada")
        job.status, job.finished_at, job.failure_reason = "falhou", _now(), reason
        session.add(_job(item, job.quantity, order, sample=job.is_sample))  # volta para a fila
    else:
        raise OrderError(f"ação desconhecida: {action}")
    await session.commit()
    await session.refresh(job)
    return job


async def advance_internal(session: AsyncSession, order: Order, new: OrderStatus) -> None:
    """Avanço automático (ex.: primeira impressão iniciada → pedido 'imprimindo')."""
    check_transition(order.status, new.value)
    order.status = new.value
    await _event(session, order, new.value, "sistema")
    await notifications.notify_customer_status(session, order, new)


def _progress(items: Sequence[OrderItem]) -> str:
    total = sum(i.quantity for i in items)
    done = sum(i.produced for i in items)
    return f"{done} de {total} impressas" if total else ""


def _summary(order: Order, items: Sequence[OrderItem]) -> dict[str, Any]:
    nxt = NEXT_STEP.get(S(order.status))
    return {
        **OrderSummary.model_validate(order).model_dump(),
        "progress": _progress(items),
        "next_step": nxt.value if nxt else None,
    }


async def list_orders(session: AsyncSession, status: str | None) -> list[OrderSummary]:
    stmt = select(Order).order_by(Order.number.desc()).limit(200)
    if status:
        stmt = stmt.where(Order.status == status)
    orders = (await session.scalars(stmt)).all()
    items = (
        await session.scalars(
            select(OrderItem).where(OrderItem.order_id.in_([o.id for o in orders]))
        )
    ).all()
    by_order: dict[int, list[OrderItem]] = defaultdict(list)
    for item in items:
        by_order[item.order_id].append(item)
    return [OrderSummary.model_validate(_summary(o, by_order[o.id])) for o in orders]


async def detail(session: AsyncSession, order_id: int) -> OrderDetail:
    order = await session.get(Order, order_id)
    if order is None:
        raise OrderError(f"pedido {order_id} não existe", not_found=True)
    items = await _items(session, order.id)
    events = (
        await session.scalars(
            select(OrderEvent).where(OrderEvent.order_id == order.id).order_by(OrderEvent.id)
        )
    ).all()
    jobs = (
        await session.scalars(
            select(PrintJob)
            .where(PrintJob.order_item_id.in_([i.id for i in items]))
            .order_by(PrintJob.id)
        )
    ).all()
    customer = await session.get(Customer, order.customer_id) if order.customer_id else None
    return OrderDetail.model_validate(
        {
            **_summary(order, items),
            "payment_method": order.payment_method,
            "public_token": order.public_token,
            "subtotal": order.subtotal,
            "shipping": order.shipping,
            "discount": order.discount,
            "sample_rounds": order.sample_rounds,
            "notes": order.notes,
            "shipping_address": order.shipping_address,
            "items": [OrderItemOut.model_validate(i) for i in items],
            "events": [OrderEventOut.model_validate(e) for e in events],
            "jobs": [PrintJobOut.model_validate(j) for j in jobs],
            "allowed": sorted(s.value for s in TRANSITIONS[S(order.status)]),
            "customer": CustomerOut.model_validate(customer) if customer else None,
        }
    )


async def print_queue(session: AsyncSession) -> list[QueueGroup]:
    """Fila do dia: por material/cor (menos trocas), dentro do grupo por prazo e pedido."""
    rows = (
        await session.execute(
            select(PrintJob, OrderItem, Order)
            .join(OrderItem, OrderItem.id == PrintJob.order_item_id)
            .join(Order, Order.id == OrderItem.order_id)
            .where(PrintJob.status.in_(OPEN_JOBS))
            .order_by(PrintJob.due_date.asc().nulls_last(), Order.number)
        )
    ).all()
    materials = {
        m.id: f"{m.kind} {m.color_name}" for m in (await session.scalars(select(Material))).all()
    }
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for job, item, order in rows:
        groups[job.material_key].append(
            {
                "job_id": job.id,
                "status": job.status,
                "order_id": order.id,
                "order_number": order.number,
                "title": item.title,
                "quantity": job.quantity,
                "is_sample": job.is_sample,
                "due_date": job.due_date.isoformat() if job.due_date else None,
                "personalization": item.personalization,
            }
        )
    return [
        QueueGroup(
            material_key=key,
            materials=[
                materials.get(int(m), f"material {m}") for m in key.split("+") if m.isdigit()
            ]
            or ["sem material definido"],
            jobs=jobs,
            total_pieces=sum(j["quantity"] for j in jobs),
        )
        for key, jobs in sorted(groups.items(), key=lambda kv: -len(kv[1]))
    ]
