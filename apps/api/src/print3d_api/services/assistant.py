"""🛍️ Assistente de compra da loja.

Busca candidatos (por significado, senão por palavra, senão novidades), pede à IA uma resposta
curta que só pode apontar para esses candidatos, e devolve os cartões com preço do banco.
O texto passa pelo Guardião; se for bloqueado, vai uma resposta neutra.
"""

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_ai import AINotConfiguredError, AITask
from print3d_ai.prompts import shop_assistant
from print3d_api.models import BrandSettings, Niche, Product
from print3d_api.models.brand import SINGLETON_ID
from print3d_api.schemas.governance import GuardianCheckIn
from print3d_api.schemas.store import StoreProductCard
from print3d_api.services import guardian, search, store
from print3d_api.services.ai import ProviderFactory, effective_settings

CANDIDATES = 8
FALLBACK = (
    "Posso te ajudar a escolher! Me conta para quem é o presente ou a ocasião "
    "(batizado, aniversário, decoração, carro...)."
)


class AssistantOut(BaseModel):
    reply: str
    products: list[StoreProductCard]
    suggestions: list[str]


async def model_for(session: AsyncSession) -> str | None:
    """Modelo do assistente: o de personalização; senão o padrão. None = desligado."""
    settings = await effective_settings(session)
    if settings.api_key is None or not settings.api_key.get_secret_value():
        return None
    for task in (AITask.PERSONALIZER, AITask.DEFAULT):
        try:
            return settings.model_for(task)
        except RuntimeError:
            continue
    return None


async def _candidates(
    session: AsyncSession,
    embedder_factory: search.EmbedderFactory,
    query: str,
    max_distance: float,
) -> list[StoreProductCard]:
    hits = await search.semantic_hits(
        session, embedder_factory, query, max_distance=max_distance, limit=CANDIDATES * 2
    )
    if hits:
        cards = await store.cards_by_ids(session, [pid for pid, _ in hits], CANDIDATES)
        if cards:
            return cards
    words = [w for w in query.split() if len(w) > 3][-1:]
    if words:
        cards = await store.list_products(
            session, niche=None, q=words[0], limit=CANDIDATES, offset=0
        )
        if cards:
            return cards
    return await store.list_products(session, niche=None, q=None, limit=CANDIDATES, offset=0)


async def ask(
    session: AsyncSession,
    factory: ProviderFactory,
    embedder_factory: search.EmbedderFactory,
    turns: list[shop_assistant.ChatTurn],
    *,
    max_distance: float,
) -> AssistantOut:
    model = await model_for(session)
    if model is None:
        raise AINotConfiguredError("assistente desligado: IA sem chave ou modelo")
    user_text = " ".join(t.content for t in turns if t.role == "user")[-600:]
    cards = await _candidates(session, embedder_factory, user_text, max_distance)
    brand = await session.get(BrandSettings, SINGLETON_ID)
    system, prompt = shop_assistant.build(
        loja=brand.name if brand else "a loja",
        voz_marca=(brand.voice or "") if brand else "",
        candidates=[(c.slug, c.title, c.niche, c.customizable) for c in cards],
        turns=turns[-10:],
    )
    settings = await effective_settings(session)
    answer = await factory(settings).complete_json(
        system=system,
        prompt=prompt,
        schema=shop_assistant.AssistantReply,
        model=model,
        max_tokens=1500,
    )
    by_slug = {c.slug: c for c in cards}
    picked = [by_slug[s] for s in dict.fromkeys(answer.product_slugs) if s in by_slug]

    niche = cards[0].niche if cards else await session.scalar(select(Niche.slug).limit(1))
    reply = answer.reply.strip() or FALLBACK
    if niche:
        decision = await guardian.decide(
            session,
            GuardianCheckIn(
                niche=niche, title="resposta do assistente", description=reply, origin="parametrico"
            ),
        )
        if not decision.approved:
            reply, picked = FALLBACK, []
    return AssistantOut(
        reply=reply,
        products=picked,
        suggestions=[s.strip() for s in answer.suggestions if s.strip()][:3],
    )


async def has_catalog(session: AsyncSession) -> bool:
    return (
        await session.scalar(
            select(Product.id)
            .where(Product.status == "ativo", Product.guardian_status == "aprovado")
            .limit(1)
        )
    ) is not None
