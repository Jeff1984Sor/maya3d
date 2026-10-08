"""Mercado Livre na operação: conectar a conta, anunciar variantes, receber pedidos e perguntas.

Regras (spec seção 2): pedido do ML nunca gera contato fora da plataforma (o pedido entra sem
cliente e sem WhatsApp); pergunta é respondida só pelo ML; tarifa vem da API do ML.
Notificações do ML não são assinadas: o que vale é o que a API do ML devolve com o NOSSO token
(conferimos conta e aplicação antes de agir).
"""

import logging
import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.models import (
    BrandSettings,
    ChannelAccount,
    ChannelCopy,
    ChannelListing,
    MarketplaceQuestion,
    Order,
    Product,
    Variant,
)
from print3d_api.models.brand import SINGLETON_ID
from print3d_api.schemas.orders import OrderCreate, OrderItemIn
from print3d_api.services import audit, content, integrations, media, notifications, orders
from print3d_channels.mercadolivre import (
    MercadoLivre,
    MercadoLivreError,
    Tokens,
    authorization_url,
    item_payload,
    pkce_pair,
)

log = logging.getLogger("print3d.ml")
CHANNEL = "mercadolivre"
STATE_TTL = 600
REFRESH_MARGIN = timedelta(minutes=10)
LISTING_TYPES = ("gold_special", "gold_pro")  # clássico | premium
DEFAULT_STOCK = 50  # sob encomenda: estoque "virtual" do anúncio


class MLError(Exception):
    def __init__(self, message: str, *, status: int = 422) -> None:
        super().__init__(message)
        self.status = status


async def _settings(session: AsyncSession) -> dict[str, str | None]:
    values = await integrations.load(session)
    keys = ("ML_CLIENT_ID", "ML_CLIENT_SECRET", "PUBLIC_API_URL", "PUBLIC_STORE_URL")
    return {k: values.get(k) or integrations.env_value(k) for k in keys}


async def client(session: AsyncSession) -> MercadoLivre:
    s = await _settings(session)
    if not s["ML_CLIENT_ID"] or not s["ML_CLIENT_SECRET"]:
        raise MLError(
            "Mercado Livre não configurado: App ID e chave secreta em Integrações", status=503
        )
    return MercadoLivre(s["ML_CLIENT_ID"], s["ML_CLIENT_SECRET"])


async def redirect_uri(session: AsyncSession) -> str:
    base = (await _settings(session))["PUBLIC_API_URL"]
    if not base or not base.startswith("https://"):
        raise MLError(
            "o Mercado Livre exige endereço HTTPS: preencha o endereço público da API "
            "(https://api.<domínio>) em Integrações",
            status=503,
        )
    return f"{base.rstrip('/')}/v1/channels/mercadolivre/callback"


# --- Conexão ---------------------------------------------------------------------------------
async def connect_url(session: AsyncSession, redis: Redis) -> str:
    ml_settings = await _settings(session)
    uri = await redirect_uri(session)
    await client(session)  # valida App ID/segredo antes de mandar o dono ao ML
    verifier, challenge = pkce_pair()
    state = secrets.token_urlsafe(24)
    await redis.set(f"print3d:ml:state:{state}", verifier, ex=STATE_TTL)
    return authorization_url(str(ml_settings["ML_CLIENT_ID"]), uri, state, challenge)


async def _save_tokens(session: AsyncSession, tokens: Tokens, nickname: str | None) -> None:
    vault = integrations.vault()
    if vault is None:
        raise MLError("servidor sem FERNET_KEY: não dá para guardar tokens", status=503)
    account = await session.get(ChannelAccount, CHANNEL)
    if account is None:
        account = ChannelAccount(channel=CHANNEL)
        session.add(account)
    account.external_user_id = tokens.user_id or account.external_user_id
    account.nickname = nickname or account.nickname
    account.access_token_enc = vault.encrypt(tokens.access_token)
    account.refresh_token_enc = vault.encrypt(tokens.refresh_token)  # uso único: sempre o novo
    account.expires_at = tokens.expires_at
    account.status = "conectada"


async def finish_connect(session: AsyncSession, redis: Redis, code: str, state: str) -> str:
    verifier = await redis.getdel(f"print3d:ml:state:{state}")
    if not verifier:
        raise MLError("link de conexão expirado ou inválido: comece de novo no painel")
    ml = await client(session)
    tokens = await ml.exchange_code(code, await redirect_uri(session), verifier.decode())
    me = await ml.me(tokens.access_token)
    await _save_tokens(session, tokens, me.get("nickname"))
    await audit.record(
        session, actor="admin", action="ml_conectado", payload={"conta": me.get("nickname")}
    )
    await session.commit()
    return str(me.get("nickname") or tokens.user_id)


async def access_token(session: AsyncSession) -> str:
    """Token válido; renova antes de vencer (com trava: o refresh token só vale uma vez)."""
    account = await session.scalar(
        select(ChannelAccount).where(ChannelAccount.channel == CHANNEL).with_for_update()
    )
    vault = integrations.vault()
    if account is None or vault is None:
        raise MLError("conta do Mercado Livre não conectada", status=409)
    if account.expires_at - REFRESH_MARGIN > datetime.now(UTC):
        return vault.decrypt(account.access_token_enc)
    ml = await client(session)
    try:
        tokens = await ml.refresh(vault.decrypt(account.refresh_token_enc))
    except MercadoLivreError as exc:
        account.status = "erro"
        await session.commit()
        raise MLError(f"reconecte a conta do Mercado Livre ({exc})", status=409) from exc
    await _save_tokens(session, tokens, None)
    await session.commit()
    return tokens.access_token


async def status(session: AsyncSession) -> dict[str, Any]:
    s = await _settings(session)
    account = await session.get(ChannelAccount, CHANNEL)
    return {
        "configured": bool(s["ML_CLIENT_ID"] and s["ML_CLIENT_SECRET"]),
        "https_ready": bool(s["PUBLIC_API_URL"] and s["PUBLIC_API_URL"].startswith("https://")),
        "pictures_ready": bool(
            s["PUBLIC_STORE_URL"] and s["PUBLIC_STORE_URL"].startswith("https://")
        ),
        "connected": account is not None and account.status == "conectada",
        "nickname": account.nickname if account else None,
        "status": account.status if account else None,
        "webhook_path": "/v1/webhooks/mercadolivre",
        "callback_path": "/v1/channels/mercadolivre/callback",
    }


# --- Anúncio ---------------------------------------------------------------------------------
async def _copy(session: AsyncSession, product: Product) -> tuple[str, str]:
    """Título/descrição: texto do ML aprovado no Redator; senão o do produto."""
    row = await session.scalar(
        select(ChannelCopy).where(
            ChannelCopy.product_id == product.id,
            ChannelCopy.channel == CHANNEL,
            ChannelCopy.status == "aprovado",
        )
    )
    if row:
        bullets = "\n".join(f"- {b}" for b in row.bullets)
        return row.title, f"{row.description}\n\n{bullets}".strip()
    return product.title, product.description or product.title


async def _pictures(session: AsyncSession, product_id: int) -> list[str]:
    base = (await _settings(session))["PUBLIC_STORE_URL"]
    if not base or not base.startswith("https://"):
        raise MLError("fotos no ML precisam de endereço HTTPS da loja (Integrações)")
    images = await content.images_of(session, product_id)
    if not images:
        raise MLError("envie ao menos uma foto do produto antes de anunciar")
    return [f"{base.rstrip('/')}{media.public_url(i.key)}" for i in images]


async def _variant(session: AsyncSession, variant_id: int) -> tuple[Variant, Product]:
    variant = await session.get(Variant, variant_id)
    product = await session.get(Product, variant.product_id) if variant else None
    if variant is None or product is None:
        raise MLError("variante não existe", status=404)
    if product.guardian_status != "aprovado":
        raise MLError("o Guardião não aprovou este produto: não dá para anunciar")
    return variant, product


async def preview(
    session: AsyncSession, variant_id: int, price: Decimal, listing_type: str
) -> dict[str, Any]:
    """Antes de publicar: categoria sugerida, atributos obrigatórios e tarifa REAL do ML."""
    _, product = await _variant(session, variant_id)
    token = await access_token(session)
    ml = await client(session)
    title, _ = await _copy(session, product)
    category = await ml.predict_category(token, title)
    if category is None:
        raise MLError("o Mercado Livre não sugeriu categoria para este título")
    fee = await ml.listing_fee(
        token, price=price, category_id=category.id, listing_type=listing_type
    )
    required = await ml.required_attributes(token, category.id)
    return {
        "title": title[:60],
        "category": {"id": category.id, "name": category.name},
        "fee": str(fee.sale_fee),
        "fee_percentage": str(fee.percentage) if fee.percentage is not None else None,
        "net": str(price - fee.sale_fee),
        "required_attributes": [{"id": a.get("id"), "name": a.get("name")} for a in required],
    }


async def publish(
    session: AsyncSession,
    variant_id: int,
    price: Decimal,
    listing_type: str,
    attributes: dict[str, str],
) -> ChannelListing:
    variant, product = await _variant(session, variant_id)
    token = await access_token(session)
    ml = await client(session)
    title, description = await _copy(session, product)
    category = await ml.predict_category(token, title)
    if category is None:
        raise MLError("o Mercado Livre não sugeriu categoria para este título")
    brand = await session.get(BrandSettings, SINGLETON_ID)
    attrs = {
        "BRAND": brand.name if brand else "Genérica",
        "MODEL": product.title[:60],
        **attributes,
    }
    listing = ChannelListing(
        product_id=product.id,
        variant_id=variant.id,
        channel=CHANNEL,
        category_id=category.id,
        listing_type=listing_type,
        price=price,
        status="rascunho",
    )
    session.add(listing)
    try:
        created = await ml.create_item(
            token,
            item_payload(
                title=title,
                category_id=category.id,
                price=price,
                quantity=DEFAULT_STOCK,
                listing_type=listing_type,
                pictures=await _pictures(session, product.id),
                attributes=[{"id": k, "value_name": v} for k, v in attrs.items() if v],
                user_products=await ml.is_user_products_seller(token),
            ),
        )
        listing.external_id = str(created["id"])
        listing.permalink = created.get("permalink")
        listing.status = "publicado"
        await ml.set_description(token, listing.external_id, description)
        fee = await ml.listing_fee(
            token, price=price, category_id=category.id, listing_type=listing_type
        )
        listing.fee = fee.sale_fee
    except MercadoLivreError as exc:
        listing.status = "erro"
        listing.last_error = "; ".join([str(exc), *exc.cause])[:2000]
    await audit.record(
        session,
        actor="admin",
        action="ml_anuncio",
        entity_type="product",
        entity_id=product.id,
        decision=listing.status,
        reason=listing.last_error,
        payload={"variante": variant.id, "preco": str(price), "tipo": listing_type},
    )
    await session.commit()
    return listing


# --- Notificações ----------------------------------------------------------------------------
async def handle_notification(session: AsyncSession, payload: dict[str, Any]) -> str:
    topic = str(payload.get("topic", ""))
    resource = str(payload.get("resource", ""))
    account = await session.get(ChannelAccount, CHANNEL)
    s = await _settings(session)
    if account is None or str(payload.get("user_id")) != account.external_user_id:
        return "ignorada: conta diferente"
    if s["ML_CLIENT_ID"] and str(payload.get("application_id")) != str(s["ML_CLIENT_ID"]):
        return "ignorada: aplicação diferente"
    token = await access_token(session)
    ml = await client(session)
    if topic == "orders_v2":
        return await _import_order(session, await ml.get(token, resource))
    if topic == "questions":
        return await _save_question(session, await ml.get(token, resource))
    return f"ignorada: tópico {topic}"


async def _import_order(session: AsyncSession, data: dict[str, Any]) -> str:
    external = str(data.get("id"))
    if data.get("status") != "paid":
        return f"pedido {external} ainda não pago"
    if await session.scalar(
        select(Order.id).where(Order.channel == CHANNEL, Order.external_id == external)
    ):
        return "pedido já importado"
    items: list[OrderItemIn] = []
    for line in data.get("order_items") or []:
        item_id = str((line.get("item") or {}).get("id"))
        listing = await session.scalar(
            select(ChannelListing).where(ChannelListing.external_id == item_id)
        )
        items.append(
            OrderItemIn(
                variant_id=listing.variant_id if listing else None,
                title=str((line.get("item") or {}).get("title", "item do Mercado Livre"))[:200],
                quantity=int(line.get("quantity", 1)),
                unit_price=Decimal(str(line.get("unit_price", 0))),
            )
        )
    if not items:
        return "pedido sem itens"
    order = await orders.create_order(
        session,
        OrderCreate(
            channel=CHANNEL,
            external_id=external,
            customer_id=None,  # sem contato fora da plataforma
            items=items,
            notes="Pedido do Mercado Livre: falar com o comprador só pelo ML.",
        ),
    )
    return f"pedido #{order.number} importado"


async def _save_question(session: AsyncSession, data: dict[str, Any]) -> str:
    external = str(data.get("id"))
    if await session.scalar(
        select(MarketplaceQuestion.id).where(MarketplaceQuestion.external_id == external)
    ):
        return "pergunta já registrada"
    item_id = str(data.get("item_id", ""))
    listing = await session.scalar(
        select(ChannelListing).where(ChannelListing.external_id == item_id)
    )
    question = MarketplaceQuestion(
        channel=CHANNEL,
        external_id=external,
        item_external_id=item_id,
        product_id=listing.product_id if listing else None,
        text=str(data.get("text", ""))[:2000],
        status="respondida" if data.get("status") == "ANSWERED" else "pendente",
        raw={k: data.get(k) for k in ("id", "item_id", "status", "date_created")},
    )
    session.add(question)
    await notifications.notify_owner(
        session,
        "pergunta_ml",
        f"Pergunta no Mercado Livre: “{question.text[:300]}”. Responda no painel.",
    )
    await session.commit()
    return "pergunta registrada"


async def answer(session: AsyncSession, question_id: int, text: str) -> MarketplaceQuestion:
    question = await session.get(MarketplaceQuestion, question_id)
    if question is None:
        raise MLError("pergunta não existe", status=404)
    if question.status == "respondida":
        raise MLError("pergunta já respondida")
    token = await access_token(session)
    ml = await client(session)
    try:
        await ml.answer(token, int(question.external_id), text)
    except MercadoLivreError as exc:
        raise MLError(f"o Mercado Livre recusou a resposta: {exc}") from exc
    question.status, question.answer = "respondida", text
    await audit.record(
        session, actor="admin", action="ml_pergunta_respondida", payload={"pergunta": question.id}
    )
    await session.commit()
    return question
