"""Loja: catálogo vendável, preço ao vivo, carrinho, frete, checkout e acompanhamento.

Vendável = ativo + aprovado pelo Guardião + impressora capaz do material mínimo + preço
calculável (gramas e tempo conhecidos e tarifa do canal do site cadastrada).
"""

import logging
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.models import (
    Cart,
    ChannelFeeBand,
    CostConfig,
    Customer,
    Design,
    Material,
    Niche,
    OpsConfig,
    Order,
    OrderEvent,
    OrderItem,
    PackagingBox,
    Payment,
    Printer,
    Product,
    ProductImage,
    Variant,
)
from print3d_api.models.orders import OPS_CONFIG_ID
from print3d_api.models.pricing import COST_CONFIG_ID
from print3d_api.schemas.governance import GuardianCheckIn
from print3d_api.schemas.orders import OrderCreate, OrderItemIn
from print3d_api.schemas.store import (
    CartIn,
    CartLine,
    CartOut,
    CheckoutIn,
    CheckoutOut,
    ColorOption,
    PixInstructions,
    PublicOrder,
    ShippingOption,
    ShippingQuote,
    StoreImage,
    StoreNiche,
    StoreProduct,
    StoreProductCard,
    StoreVariant,
    TimelineEntry,
)
from print3d_api.services import guardian, media, orders, payments, search
from print3d_api.services.cep import CepProvider
from print3d_api.services.pricing import margin_for, select_bands
from print3d_channels.mercadopago import MercadoPagoError
from print3d_channels.shipping import Parcel, ShippingError, ShippingQuoter, parcel_from_mm
from print3d_core import CostInputs, FeeBand, PricingError, ProfitRule, compute_cost, quote_channel
from print3d_core.guardian import material_available
from print3d_core.orders import CUSTOMER_LABELS, OrderStatus

PIX_CHANNEL, CARD_CHANNEL = "site_pix", "site_card"


log = logging.getLogger("print3d.store")


class StoreError(Exception):
    def __init__(self, message: str, *, not_found: bool = False) -> None:
        super().__init__(message)
        self.not_found = not_found


# --- Preço ao vivo -------------------------------------------------------------------------
@dataclass
class PriceContext:
    config: CostConfig | None
    printer: Printer | None
    materials: dict[int, Material]
    bands: dict[str, list[FeeBand]]
    bands_by_category: dict[str | None, dict[str, list[FeeBand]]]
    raw_bands: Sequence[ChannelFeeBand]
    packaging: dict[int, PackagingBox]
    printable: set[str]

    def bands_for(self, category: str) -> dict[str, list[FeeBand]]:
        if category not in self.bands_by_category:
            self.bands_by_category[category] = select_bands(self.raw_bands, category)
        return self.bands_by_category[category]


async def load_context(session: AsyncSession) -> PriceContext:
    printers = (await session.scalars(select(Printer).order_by(Printer.id))).all()
    active = [p for p in printers if p.status == "ativa"]
    raw = (
        await session.scalars(
            select(ChannelFeeBand).where(ChannelFeeBand.channel.in_([PIX_CHANNEL, CARD_CHANNEL]))
        )
    ).all()
    return PriceContext(
        config=await session.get(CostConfig, COST_CONFIG_ID),
        printer=active[0] if active else (printers[0] if printers else None),
        materials={m.id: m for m in (await session.scalars(select(Material))).all()},
        bands=select_bands(raw, None),
        bands_by_category={},
        raw_bands=raw,
        packaging={b.id: b for b in (await session.scalars(select(PackagingBox))).all()},
        printable={k.upper() for p in active for k in p.supported_materials},
    )


def price_variant(ctx: PriceContext, variant: Variant, category: str) -> dict[str, Decimal | None]:
    """Preço Pix e cartão do site. None quando faltam dados (nunca chuta)."""
    out: dict[str, Decimal | None] = {"pix": None, "card": None}
    if not (ctx.config and ctx.printer and variant.grams_by_material and variant.print_seconds):
        return out
    try:
        grams = {k: Decimal(str(v)) for k, v in variant.grams_by_material.items()}
        prices = {k: ctx.materials[int(k)].price_per_kg for k in grams}
    except (KeyError, ValueError):
        return out
    extras = Decimal(0)
    if variant.packaging_id and variant.packaging_id in ctx.packaging:
        extras = ctx.packaging[variant.packaging_id].cost
    try:
        cost = compute_cost(
            CostInputs(
                grams_by_material=grams,
                price_per_kg=prices,
                print_hours=Decimal(variant.print_seconds) / 3600,
                printer_watts=Decimal(ctx.printer.avg_watts),
                energy_price_kwh=ctx.config.energy_price_kwh,
                printer_hourly_wear=ctx.printer.hourly_wear,
                post_minutes=Decimal(variant.post_minutes),
                labor_per_hour=ctx.config.labor_per_hour,
                failure_rate=ctx.config.failure_rate,
                extra_costs=extras,
            )
        )
    except PricingError:
        return out
    rule = ProfitRule(ctx.config.min_profit, margin_for(ctx.config, category))
    bands = ctx.bands_for(category)
    for key, channel in (("pix", PIX_CHANNEL), ("card", CARD_CHANNEL)):
        try:
            out[key] = quote_channel(channel, cost.total, bands.get(channel, []), rule).price
        except PricingError:
            out[key] = None
    return out


def _colors(ctx: PriceContext, variant: Variant) -> list[ColorOption]:
    """Cores oferecidas: materiais ativos e com estoque do mesmo tipo do material da variante."""
    kinds = {
        ctx.materials[int(k)].kind
        for k in (variant.grams_by_material or {})
        if int(k) in ctx.materials
    }
    return [
        ColorOption(material_id=m.id, name=m.color_name, hex=m.color_hex, kind=m.kind)
        for m in sorted(ctx.materials.values(), key=lambda m: (m.kind, m.color_name))
        if m.active and m.stock_grams > 0 and m.kind in kinds
    ]


# --- Catálogo ------------------------------------------------------------------------------
def _sellable_stmt() -> Any:
    return select(Product).where(Product.status == "ativo", Product.guardian_status == "aprovado")


async def _variants(session: AsyncSession, product_ids: Sequence[int]) -> dict[int, list[Variant]]:
    out: dict[int, list[Variant]] = {pid: [] for pid in product_ids}
    if product_ids:
        rows = await session.scalars(
            select(Variant).where(Variant.product_id.in_(product_ids)).order_by(Variant.id)
        )
        for v in rows.all():
            out[v.product_id].append(v)
    return out


async def _images(
    session: AsyncSession, product_ids: Sequence[int]
) -> dict[int, list[ProductImage]]:
    out: dict[int, list[ProductImage]] = {pid: [] for pid in product_ids}
    if product_ids:
        rows = await session.scalars(
            select(ProductImage)
            .where(ProductImage.product_id.in_(product_ids))
            .order_by(ProductImage.position, ProductImage.id)
        )
        for img in rows.all():
            out[img.product_id].append(img)
    return out


async def _cards(
    session: AsyncSession, ctx: PriceContext, products: Sequence[Product]
) -> list[StoreProductCard]:
    ids = [p.id for p in products]
    variants, images = await _variants(session, ids), await _images(session, ids)
    return [
        _card(ctx, p, variants[p.id], images[p.id][0].thumb_key if images[p.id] else None)
        for p in products
    ]


def _card(
    ctx: PriceContext, product: Product, variants: list[Variant], image_key: str | None = None
) -> StoreProductCard:
    prices = [price_variant(ctx, v, product.category)["pix"] for v in variants]
    priced = [p for p in prices if p is not None]
    hexes = {c.hex for v in variants for c in _colors(ctx, v)}
    return StoreProductCard(
        slug=product.slug,
        title=product.title,
        niche=product.niche,
        category=product.category,
        customizable=product.customizable,
        price_from=min(priced) if priced else None,
        colors=sorted(hexes)[:8],
        image=media.public_url(image_key),
    )


async def cards_by_ids(
    session: AsyncSession, ids: Sequence[int], limit: int
) -> list[StoreProductCard]:
    """Cartões na ordem dada, só dos produtos que continuam à venda."""
    if not ids:
        return []
    rows = {p.id: p for p in (await session.scalars(_sellable_stmt().where(Product.id.in_(ids))))}
    ctx = await load_context(session)
    products = [
        rows[i]
        for i in ids
        if i in rows and material_available(rows[i].min_material, ctx.printable)
    ][:limit]
    return await _cards(session, ctx, products)


async def list_products(
    session: AsyncSession,
    *,
    niche: str | None,
    q: str | None,
    limit: int,
    offset: int,
    semantic_ids: Sequence[int] | None = None,
) -> list[StoreProductCard]:
    """Busca por palavra; com `semantic_ids` (busca por significado), soma os parecidos
    depois dos resultados exatos (só na primeira página)."""
    stmt = _sellable_stmt().order_by(Product.updated_at.desc())
    if niche:
        stmt = stmt.where(Product.niche == niche)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                func.unaccent(Product.title).ilike(func.unaccent(like)),
                func.unaccent(Product.category).ilike(func.unaccent(like)),
                func.unaccent(cast(Product.tags, String)).ilike(func.unaccent(like)),
            )
        )
    if q and semantic_ids and offset == 0:
        literal = (await session.scalars(stmt.with_only_columns(Product.id).limit(limit))).all()
        return await cards_by_ids(session, search.merge_ranked(literal, semantic_ids), limit)
    products = (await session.scalars(stmt.limit(limit * 2).offset(offset))).all()
    ctx = await load_context(session)
    products = [p for p in products if material_available(p.min_material, ctx.printable)][:limit]
    return await _cards(session, ctx, products)


async def section_cards(
    session: AsyncSession, kind: str, value: str, limit: int
) -> list[StoreProductCard]:
    """Vitrine da página inicial: novidades, por nicho, categoria, tag ou escolhidos a dedo."""
    stmt = _sellable_stmt().order_by(Product.updated_at.desc())
    value = value.strip()
    if kind == "niche" and value:
        stmt = stmt.where(Product.niche == value)
    elif kind == "category" and value:
        stmt = stmt.where(Product.category == value)
    elif kind == "tag" and value:
        stmt = stmt.where(Product.tags.contains([value]))
    elif kind == "manual":
        slugs = [s.strip() for s in value.split(",") if s.strip()][:24]
        if not slugs:
            return []
        rows = {p.slug: p for p in (await session.scalars(stmt.where(Product.slug.in_(slugs))))}
        ctx = await load_context(session)
        chosen = [
            rows[s]
            for s in slugs
            if s in rows and material_available(rows[s].min_material, ctx.printable)
        ]
        return await _cards(session, ctx, chosen[:limit])
    products = (await session.scalars(stmt.limit(limit * 2))).all()
    ctx = await load_context(session)
    products = [p for p in products if material_available(p.min_material, ctx.printable)][:limit]
    return await _cards(session, ctx, products)


async def list_niches(session: AsyncSession) -> list[StoreNiche]:
    niches = (
        await session.scalars(select(Niche).where(Niche.active).order_by(Niche.sort_order))
    ).all()
    counts = dict(
        (
            await session.execute(
                _sellable_stmt()
                .with_only_columns(Product.niche, func.count())
                .group_by(Product.niche)
            )
        ).all()
    )
    return [
        StoreNiche(slug=n.slug, name=n.name, products=int(counts.get(n.slug, 0))) for n in niches
    ]


async def product_detail(session: AsyncSession, slug: str) -> StoreProduct:
    product = await session.scalar(_sellable_stmt().where(Product.slug == slug))
    ctx = await load_context(session)
    if product is None or not material_available(product.min_material, ctx.printable):
        raise StoreError("produto não encontrado", not_found=True)
    variants = (await _variants(session, [product.id]))[product.id]
    design = await session.get(Design, product.design_id)
    model = (design.params_schema or {}).get("model") if design else None
    attribution = None
    if product.attribution_required and design:
        attribution = design.attribution_text or (
            f"Modelo de {design.author}" if design.author else None
        )
    images = (await _images(session, [product.id]))[product.id]
    card = _card(ctx, product, variants, images[0].thumb_key if images else None)
    return StoreProduct(
        **card.model_dump(),
        description=product.description,
        tags=list(product.tags),
        disclaimers=list(product.disclaimers),
        attribution=attribution,
        age_rating=product.age_rating,
        variants=[
            StoreVariant(
                id=v.id,
                sku=v.sku,
                label=" · ".join(
                    x
                    for x in (v.size_label, "pintada à mão" if v.finish == "pintada" else None)
                    if x
                )
                or "Padrão",
                finish=v.finish,
                price_pix=(p := price_variant(ctx, v, product.category))["pix"],
                price_card=p["card"],
                colors=_colors(ctx, v),
            )
            for v in variants
        ],
        parametric_model=str(model) if model else None,
        model3d=bool(design and (design.source_file_url or "").startswith("library/")),
        images=[
            StoreImage(
                url=media.public_url(i.key) or "",
                thumb=media.public_url(i.thumb_key) or "",
                alt=i.alt or product.title,
            )
            for i in images
        ],
    )


# --- Carrinho ------------------------------------------------------------------------------
async def create_cart(session: AsyncSession) -> str:
    token = secrets.token_urlsafe(18)
    session.add(Cart(token=token, items=[]))
    await session.commit()
    return token


async def _cart(session: AsyncSession, token: str) -> Cart:
    cart = await session.get(Cart, token)
    if cart is None:
        raise StoreError("carrinho não encontrado", not_found=True)
    return cart


async def cart_view(session: AsyncSession, token: str) -> CartOut:
    cart = await _cart(session, token)
    ctx = await load_context(session)
    lines: list[CartLine] = []
    problems: list[str] = []
    subtotal = Decimal(0)
    for raw in cart.items:
        variant = await session.get(Variant, int(raw["variant_id"]))
        product = await session.get(Product, variant.product_id) if variant else None
        if variant is None or product is None or product.status != "ativo":
            problems.append("um item saiu de linha e foi ignorado")
            continue
        price = price_variant(ctx, variant, product.category)["pix"]
        material_id = raw.get("material_id")
        color = next((c for c in _colors(ctx, variant) if c.material_id == material_id), None)
        if material_id is not None and color is None:
            problems.append(f"a cor escolhida de '{product.title}' acabou: escolha outra")
        qty = int(raw["quantity"])
        line_total = price * qty if price is not None else None
        if line_total is None:
            problems.append(f"'{product.title}' está sem preço no momento")
        else:
            subtotal += line_total
        lines.append(
            CartLine(
                variant_id=variant.id,
                product_slug=product.slug,
                title=f"{product.title} {variant.size_label or ''}".strip(),
                quantity=qty,
                material_id=material_id,
                color=color,
                personalization=dict(raw.get("personalization") or {}),
                unit_price=price,
                line_total=line_total,
            )
        )
    return CartOut(
        token=token,
        items=lines,
        subtotal=subtotal,
        purchasable=bool(lines) and not problems,
        problems=sorted(set(problems)),
    )


async def set_cart(session: AsyncSession, token: str, data: CartIn) -> CartOut:
    cart = await _cart(session, token)
    for line in data.items:
        variant = await session.get(Variant, line.variant_id)
        product = await session.get(Product, variant.product_id) if variant else None
        if variant is None or product is None:
            raise StoreError(f"variante {line.variant_id} não existe", not_found=True)
        texts = [v for v in line.personalization.values() if v.strip()]
        if texts:
            decision = await guardian.decide(
                session,
                GuardianCheckIn(
                    niche=product.niche,
                    title=product.title,
                    origin="parametrico",
                    customer_text=texts,
                ),
            )
            if not decision.approved:
                raise StoreError(
                    "texto de personalização não permitido: "
                    + "; ".join(v.message for v in decision.violations)
                )
    cart.items = [line.model_dump() for line in data.items]
    await session.commit()
    return await cart_view(session, token)


# --- Frete ---------------------------------------------------------------------------------
DEFAULT_BOX_MM = (160.0, 110.0, 60.0)  # sem embalagem cadastrada: caixa pequena padrão
DEFAULT_WEIGHT_G = 300.0


async def _parcels(session: AsyncSession, cart_token: str) -> list[Parcel]:
    """Uma caixa por item do carrinho, com medidas da embalagem e peso embalado da variante."""
    cart = await session.get(Cart, cart_token)
    if cart is None or not cart.items:
        return []
    ids = [int(i["variant_id"]) for i in cart.items]
    variants = {
        v.id: v for v in (await session.scalars(select(Variant).where(Variant.id.in_(ids))))
    }
    boxes = {b.id: b for b in (await session.scalars(select(PackagingBox))).all()}
    view = await cart_view(session, cart_token)
    prices = {line.variant_id: line.unit_price or Decimal(0) for line in view.items}
    parcels = []
    for item in cart.items:
        variant = variants.get(int(item["variant_id"]))
        if variant is None:
            continue
        box = boxes.get(variant.packaging_id) if variant.packaging_id else None
        dims = (
            (box.inner_x_mm + 4.0, box.inner_y_mm + 4.0, box.inner_z_mm + 4.0)
            if box
            else DEFAULT_BOX_MM
        )
        grams = sum((variant.grams_by_material or {}).values())
        weight = variant.packed_weight_g or (
            (box.weight_g + grams) if box and grams else DEFAULT_WEIGHT_G
        )
        parcels.append(
            parcel_from_mm(
                f"v{variant.id}",
                dims,
                float(weight),
                prices.get(variant.id, Decimal(0)),
                int(item.get("quantity", 1)),
            )
        )
    return parcels


async def _carrier_options(
    session: AsyncSession,
    quoter: ShippingQuoter | None,
    origin_cep: str | None,
    dest_cep: str,
    cart_token: str | None,
) -> tuple[list[ShippingOption], str | None]:
    """Opções do Melhor Envio. Devolve (opções, motivo de não ter cotação automática)."""
    if quoter is None or not origin_cep:
        return [], "frete automático ainda não configurado"
    if not cart_token:
        return [], None
    parcels = await _parcels(session, cart_token)
    if not parcels:
        return [], None
    try:
        rates = await quoter.quote(origin_cep, dest_cep, parcels)
    except ShippingError as exc:
        log.warning("cotação de frete falhou", extra={"erro": str(exc)})
        return [], "cálculo automático indisponível agora"
    return [
        ShippingOption(
            id=f"me-{r.service_id}",
            label=f"{r.carrier} {r.service}".strip(),
            price=r.price,
            detail=f"até {r.days} dias úteis após a postagem" if r.days else "",
        )
        for r in rates[:6]
    ], None


async def quote_shipping(
    session: AsyncSession,
    cep_provider: CepProvider,
    cep: str,
    subtotal: Decimal,
    *,
    cart_token: str | None = None,
    quoter: ShippingQuoter | None = None,
) -> ShippingQuote:
    ops = await session.get(OpsConfig, OPS_CONFIG_ID)
    address = await cep_provider.lookup(cep)
    local = bool(ops and address.ibge in ops.local_cities_ibge)
    options: list[ShippingOption] = []
    free_min = ops.local_free_shipping_min if ops else None
    missing = None
    if local and ops:
        free = subtotal >= ops.local_free_shipping_min
        missing = None if free else ops.local_free_shipping_min - subtotal
        options.append(
            ShippingOption(
                id="local",
                label=f"Entrega local em {address.city}",
                price=Decimal(0) if free else ops.local_delivery_fee,
                detail="grátis" if free else f"grátis a partir de R$ {ops.local_free_shipping_min}",
            )
        )
        if ops.pickup_enabled:
            options.append(
                ShippingOption(id="retirada", label="Retirar no local", price=Decimal(0))
            )
    if not local:  # local já tem entrega própria; fora daqui, Correios/transportadoras
        carriers, reason = await _carrier_options(
            session, quoter, ops.origin_cep if ops else None, address.cep, cart_token
        )
        options.extend(carriers)
        if not carriers:
            detail = "valor informado pelo WhatsApp após o pedido"
            options.append(
                ShippingOption(
                    id="envio",
                    label="Envio pelos Correios/transportadora",
                    price=None,
                    detail=f"{detail} ({reason})" if reason else detail,
                )
            )
    return ShippingQuote(
        cep=address.cep,
        city=address.city,
        uf=address.uf,
        street=address.street,
        district=address.district,
        local=local,
        options=options,
        free_shipping_min=free_min if local else None,
        missing_for_free=missing,
    )


# --- Checkout ------------------------------------------------------------------------------
async def checkout(
    session: AsyncSession,
    cep_provider: CepProvider,
    data: CheckoutIn,
    quoter: ShippingQuoter | None = None,
) -> CheckoutOut:
    if not data.accept_terms:
        raise StoreError("é preciso aceitar os termos e a política de privacidade")
    view = await cart_view(session, data.cart_token)
    if not view.purchasable:
        raise StoreError("; ".join(view.problems) or "carrinho vazio")
    # o preço do frete vem desta recotação no servidor, nunca do navegador
    quote = await quote_shipping(
        session, cep_provider, data.cep, view.subtotal, cart_token=data.cart_token, quoter=quoter
    )
    option = next((o for o in quote.options if o.id == data.shipping_option), None)
    if option is None:
        raise StoreError("opção de entrega indisponível para este CEP")

    customer = await session.scalar(select(Customer).where(Customer.email == data.email))
    if customer is None:
        customer = Customer(kind="pf", name=data.name, email=data.email, source="site")
        session.add(customer)
    customer.name = data.name
    customer.whatsapp = data.whatsapp
    customer.whatsapp_opt_in = data.whatsapp_opt_in
    customer.marketing_opt_in = data.marketing_opt_in
    await session.flush()

    order = await orders.create_order(
        session,
        OrderCreate(
            channel="site",
            customer_id=customer.id,
            items=[
                OrderItemIn(
                    variant_id=line.variant_id,
                    quantity=line.quantity,
                    unit_price=line.unit_price or Decimal(0),
                    personalization=line.personalization,
                    material_ids=[line.material_id] if line.material_id else [],
                )
                for line in view.items
            ],
            shipping=option.price or Decimal(0),
            shipping_address={
                "cep": quote.cep,
                "street": data.street,
                "number": data.number,
                "complement": data.complement,
                "district": data.district,
                "city": quote.city,
                "uf": quote.uf,
                "option": option.id,
                "option_label": option.label,
            },
            local_delivery=option.id == "local",
            notes=data.notes,
        ),
        awaiting_payment=True,
        payment_method="pix_manual",
    )
    cart = await session.get(Cart, data.cart_token)
    if cart is not None:
        cart.items = []
    await session.commit()
    # Pix automático (Mercado Pago). Se o gateway falhar, o pedido segue com o Pix manual.
    payment = None
    if option.price is not None:  # frete "a combinar": total ainda vai mudar, cobra depois
        try:
            payment = await payments.charge_pix(session, order, customer)
            await session.commit()
        except MercadoPagoError as exc:
            await session.rollback()
            log.warning("Pix automático indisponível", extra={"pedido": order.id, "erro": str(exc)})
    ops = await session.get(OpsConfig, OPS_CONFIG_ID)
    return CheckoutOut(
        order_number=order.number,
        public_token=order.public_token or "",
        total=order.total,
        shipping_pending=option.price is None,
        pix=_pix(ops, order, payment),
    )


def _pix(ops: OpsConfig | None, order: Order, payment: Payment | None) -> PixInstructions:
    if payment is not None:
        return PixInstructions(
            key=None,
            name=None,
            amount=order.total,
            automatic=True,
            qr_code=payment.qr_code,
            qr_code_base64=payment.qr_code_base64,
            expires_at=payment.expires_at,
        )
    return PixInstructions(
        key=ops.pix_key if ops else None, name=ops.pix_name if ops else None, amount=order.total
    )


# --- Acompanhamento ------------------------------------------------------------------------
async def public_order(session: AsyncSession, token: str) -> PublicOrder:
    order = await session.scalar(select(Order).where(Order.public_token == token))
    if order is None:
        raise StoreError("pedido não encontrado", not_found=True)
    items = (await session.scalars(select(OrderItem).where(OrderItem.order_id == order.id))).all()
    events = (
        await session.scalars(
            select(OrderEvent).where(OrderEvent.order_id == order.id).order_by(OrderEvent.id)
        )
    ).all()
    status = OrderStatus(order.status)
    ops = await session.get(OpsConfig, OPS_CONFIG_ID)
    total_qty = sum(i.quantity for i in items)
    return PublicOrder(
        number=order.number,
        status=status.value,
        status_label=CUSTOMER_LABELS[status],
        total=order.total,
        shipping=order.shipping,
        items=[
            {"title": i.title, "quantity": i.quantity, "personalization": i.personalization}
            for i in items
        ],
        timeline=[
            TimelineEntry(
                at=e.created_at,
                status=e.status,
                label=CUSTOMER_LABELS.get(OrderStatus(e.status), e.status),
                media_url=e.media_url,
            )
            for e in events
        ],
        progress=f"{sum(i.produced for i in items)} de {total_qty} prontas" if total_qty else "",
        pix=_pix(ops, order, await payments.current_pix(session, order.id))
        if status is OrderStatus.AGUARDANDO_PAGAMENTO
        else None,
    )
