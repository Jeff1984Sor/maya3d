"""Shopee na operação: conectar a loja, anunciar variantes e receber pedidos pagos (push).

Mesmas regras do Mercado Livre: pedido sem contato fora da plataforma; comissão vem da
tabela de tarifas (canal "shopee"), nunca do código. O push é verificado pela assinatura
(HMAC com a chave do parceiro) e o pedido é relido na API da Shopee com o NOSSO token.
"""

import asyncio
import io
import logging
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from PIL import Image
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.models import (
    ChannelAccount,
    ChannelCopy,
    ChannelListing,
    Order,
    PackagingBox,
    Product,
    Variant,
)
from print3d_api.schemas.orders import OrderCreate, OrderItemIn
from print3d_api.services import audit, content, integrations, orders
from print3d_channels.shopee import (
    DEFAULT_HOST,
    PAID_STATUSES,
    Shopee,
    ShopeeError,
    ShopTokens,
    item_payload,
    verify_push,
)
from print3d_core.storage import LocalStorage

log = logging.getLogger("print3d.shopee")
CHANNEL = "shopee"
STATE_TTL = 600
REFRESH_MARGIN = timedelta(minutes=10)
DEFAULT_STOCK = 50
DEFAULT_BOX_CM = (16, 11, 6)
DEFAULT_WEIGHT_KG = 0.3


class ShopeeServiceError(Exception):
    def __init__(self, message: str, *, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


async def _settings(session: AsyncSession) -> dict[str, str | None]:
    values = await integrations.load(session)
    keys = ("SHOPEE_PARTNER_ID", "SHOPEE_PARTNER_KEY", "SHOPEE_HOST", "PUBLIC_API_URL")
    return {k: values.get(k) or integrations.env_value(k) for k in keys}


async def client(session: AsyncSession) -> Shopee:
    s = await _settings(session)
    pid, key = s["SHOPEE_PARTNER_ID"], s["SHOPEE_PARTNER_KEY"]
    if not pid or not key or not pid.isdigit():
        raise ShopeeServiceError(
            "Shopee não configurada: Partner ID e Partner Key em Integrações", status=503
        )
    return Shopee(int(pid), key, host=s["SHOPEE_HOST"] or DEFAULT_HOST)


async def _public_api(session: AsyncSession) -> str:
    base = (await _settings(session))["PUBLIC_API_URL"]
    if not base or not base.startswith("https://"):
        raise ShopeeServiceError(
            "a Shopee exige endereço HTTPS: preencha o endereço público da API em Integrações",
            status=503,
        )
    return base.rstrip("/")


async def connect_url(session: AsyncSession, redis: Redis) -> str:
    sh = await client(session)
    state = secrets.token_urlsafe(24)
    await redis.set(f"print3d:shopee:state:{state}", "1", ex=STATE_TTL)
    return sh.authorization_url(
        f"{await _public_api(session)}/v1/channels/shopee/callback?state={state}"
    )


async def _save(session: AsyncSession, tokens: ShopTokens, name: str | None) -> None:
    vault = integrations.vault()
    if vault is None:
        raise ShopeeServiceError("servidor sem FERNET_KEY: não dá para guardar tokens", status=503)
    account = await session.get(ChannelAccount, CHANNEL) or ChannelAccount(channel=CHANNEL)
    session.add(account)
    account.external_user_id = tokens.shop_id
    account.nickname = name or account.nickname
    account.access_token_enc = vault.encrypt(tokens.access_token)
    account.refresh_token_enc = vault.encrypt(tokens.refresh_token)
    account.expires_at = tokens.expires_at
    account.status = "conectada"


async def finish_connect(
    session: AsyncSession, redis: Redis, code: str, shop_id: str, state: str
) -> str:
    if not await redis.getdel(f"print3d:shopee:state:{state}"):
        raise ShopeeServiceError("link de conexão expirado ou inválido: comece de novo no painel")
    sh = await client(session)
    tokens = await sh.exchange_code(code, shop_id)
    info = await sh.shop_info(tokens.access_token, shop_id)
    name = str(info.get("shop_name") or shop_id)
    await _save(session, tokens, name)
    await audit.record(session, actor="admin", action="shopee_conectada", payload={"loja": name})
    await session.commit()
    return name


async def access_token(session: AsyncSession) -> tuple[str, str]:
    """(token, shop_id) válidos; renova antes de vencer, com trava."""
    account = await session.scalar(
        select(ChannelAccount).where(ChannelAccount.channel == CHANNEL).with_for_update()
    )
    vault = integrations.vault()
    if account is None or vault is None:
        raise ShopeeServiceError("loja da Shopee não conectada", status=409)
    if account.expires_at - REFRESH_MARGIN > datetime.now(UTC):
        return vault.decrypt(account.access_token_enc), account.external_user_id
    sh = await client(session)
    try:
        tokens = await sh.refresh(
            vault.decrypt(account.refresh_token_enc), account.external_user_id
        )
    except ShopeeError as exc:
        account.status = "erro"
        await session.commit()
        raise ShopeeServiceError(f"reconecte a loja da Shopee ({exc})", status=409) from exc
    await _save(session, tokens, None)
    await session.commit()
    return tokens.access_token, tokens.shop_id


async def status(session: AsyncSession) -> dict[str, Any]:
    s = await _settings(session)
    account = await session.get(ChannelAccount, CHANNEL)
    return {
        "configured": bool(s["SHOPEE_PARTNER_ID"] and s["SHOPEE_PARTNER_KEY"]),
        "https_ready": bool(s["PUBLIC_API_URL"] and s["PUBLIC_API_URL"].startswith("https://")),
        "connected": account is not None and account.status == "conectada",
        "shop": account.nickname if account else None,
        "status": account.status if account else None,
        "webhook_path": "/v1/webhooks/shopee",
        "callback_path": "/v1/channels/shopee/callback",
    }


def _jpeg(data: bytes) -> bytes:
    """Fotos da loja são WebP; a Shopee recebe JPG."""
    img = Image.open(io.BytesIO(data)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=90)
    return buf.getvalue()


async def publish(
    session: AsyncSession, storage: LocalStorage, variant_id: int, price: Decimal
) -> ChannelListing:
    variant = await session.get(Variant, variant_id)
    product = await session.get(Product, variant.product_id) if variant else None
    if variant is None or product is None:
        raise ShopeeServiceError("variante não existe", status=404)
    if product.guardian_status != "aprovado":
        raise ShopeeServiceError("o Guardião não aprovou este produto: não dá para anunciar")
    images = await content.images_of(session, product.id)
    if not images:
        raise ShopeeServiceError("envie ao menos uma foto do produto antes de anunciar")
    token, shop_id = await access_token(session)
    sh = await client(session)

    copy = await session.scalar(
        select(ChannelCopy).where(
            ChannelCopy.product_id == product.id,
            ChannelCopy.channel == CHANNEL,
            ChannelCopy.status == "aprovado",
        )
    )
    name = copy.title if copy else product.title
    description = (
        f"{copy.description}\n\n" + "\n".join(f"- {b}" for b in copy.bullets) if copy else ""
    ).strip() or (product.description or product.title)

    box = await session.get(PackagingBox, variant.packaging_id) if variant.packaging_id else None
    dims = (
        tuple(
            max(1, -(-int(v + 4) // 10)) for v in (box.inner_x_mm, box.inner_y_mm, box.inner_z_mm)
        )
        if box
        else DEFAULT_BOX_CM
    )
    grams = sum((variant.grams_by_material or {}).values())
    weight = (variant.packed_weight_g or ((box.weight_g + grams) if box and grams else 0)) / 1000

    listing = ChannelListing(
        product_id=product.id,
        variant_id=variant.id,
        channel=CHANNEL,
        price=price,
        status="rascunho",
    )
    session.add(listing)
    try:
        category = await sh.recommend_category(token, shop_id, name)
        if category is None:
            raise ShopeeError("a Shopee não sugeriu categoria para este nome")
        listing.category_id = str(category)
        image_ids = []
        for img in images[:9]:
            raw = await asyncio.to_thread(storage.local_path(img.key).read_bytes)
            image_ids.append(await sh.upload_image(_jpeg(raw)))
        logistic_ids = await sh.logistics(token, shop_id)
        if not logistic_ids:
            raise ShopeeError("nenhum canal de envio ativo na loja da Shopee")
        item_id = await sh.add_item(
            token,
            shop_id,
            item_payload(
                name=name,
                description=description,
                price=price,
                stock=DEFAULT_STOCK,
                category_id=category,
                image_ids=image_ids,
                weight_kg=weight or DEFAULT_WEIGHT_KG,
                dims_cm=(int(dims[0]), int(dims[1]), int(dims[2])),
                logistic_ids=logistic_ids,
            ),
        )
        listing.external_id = f"shopee-{item_id}"
        listing.status = "publicado"
    except ShopeeError as exc:
        listing.status = "erro"
        listing.last_error = str(exc)[:2000]
    await audit.record(
        session,
        actor="admin",
        action="shopee_anuncio",
        entity_type="product",
        entity_id=product.id,
        decision=listing.status,
        reason=listing.last_error,
        payload={"variante": variant.id, "preco": str(price)},
    )
    await session.commit()
    return listing


# --- Push (webhook) --------------------------------------------------------------------------
async def verify(session: AsyncSession, raw: bytes, authorization: str | None) -> bool:
    s = await _settings(session)
    if not s["SHOPEE_PARTNER_KEY"] or not s["PUBLIC_API_URL"]:
        return False
    url = f"{s['PUBLIC_API_URL'].rstrip('/')}/v1/webhooks/shopee"
    return verify_push(s["SHOPEE_PARTNER_KEY"], url, raw, authorization)


async def handle_push(session: AsyncSession, payload: dict[str, Any]) -> str:
    account = await session.get(ChannelAccount, CHANNEL)
    if account is None or str(payload.get("shop_id")) != account.external_user_id:
        return "ignorada: loja diferente"
    if payload.get("code") != 3:  # 3 = mudança de status do pedido
        return f"ignorada: código {payload.get('code')}"
    data = payload.get("data") or {}
    order_sn = str(data.get("ordersn", ""))
    if not order_sn or str(data.get("status")) not in PAID_STATUSES:
        return "pedido ainda não pago"
    if await session.scalar(
        select(Order.id).where(Order.channel == CHANNEL, Order.external_id == order_sn)
    ):
        return "pedido já importado"
    token, shop_id = await access_token(session)
    detail = await (await client(session)).order_detail(token, shop_id, order_sn)
    items: list[OrderItemIn] = []
    for line in detail.get("item_list") or []:
        listing = await session.scalar(
            select(ChannelListing).where(
                ChannelListing.external_id == f"shopee-{line.get('item_id')}"
            )
        )
        items.append(
            OrderItemIn(
                variant_id=listing.variant_id if listing else None,
                title=str(line.get("item_name", "item da Shopee"))[:200],
                quantity=int(line.get("model_quantity_purchased", 1)),
                unit_price=Decimal(
                    str(line.get("model_discounted_price", line.get("model_original_price", 0)))
                ),
            )
        )
    if not items:
        return "pedido sem itens"
    order = await orders.create_order(
        session,
        OrderCreate(
            channel=CHANNEL,
            external_id=order_sn,
            customer_id=None,
            items=items,
            notes="Pedido da Shopee: falar com o comprador só pela Shopee.",
        ),
    )
    return f"pedido #{order.number} importado"
