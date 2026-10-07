"""Busca semântica do catálogo (pgvector). Cada produto vira um texto → vetor; a busca
compara a frase do cliente com esses vetores. Sem IA configurada, a loja segue com a busca
por palavras (unaccent/ilike) — nada quebra.
"""

import asyncio
import hashlib
import logging
from collections import OrderedDict
from collections.abc import Callable, Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from print3d_ai import AINotConfiguredError, AISettings, AITask, EmbeddingProvider
from print3d_ai.embeddings import make_embedder
from print3d_api.models import Niche, Product, ProductEmbedding
from print3d_api.services.ai import effective_settings

log = logging.getLogger("print3d.search")
EmbedderFactory = Callable[[AISettings], EmbeddingProvider]
_QUERY_CACHE: OrderedDict[tuple[str, str], list[float]] = OrderedDict()
_CACHE_MAX = 256


def default_embedder_factory(settings: AISettings) -> EmbeddingProvider:
    return make_embedder(settings)


def product_text(product: Product, niche_name: str | None) -> str:
    parts = [
        product.title,
        f"Nicho: {niche_name or product.niche}",
        f"Categoria: {product.category.replace('-', ' ')}",
        f"Subcategoria: {product.subcategory.replace('-', ' ')}" if product.subcategory else "",
        "Personalizável com nome ou frase" if product.customizable else "",
        f"Tags: {', '.join(product.tags)}" if product.tags else "",
        f"Ocasiões: {', '.join(product.occasions)}" if product.occasions else "",
        (product.description or "")[:1500],
    ]
    return "\n".join(p for p in parts if p)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def setup(
    session: AsyncSession, factory: EmbedderFactory
) -> tuple[EmbeddingProvider, str] | None:
    """(embedder, modelo) ou None quando a busca semântica não está configurada."""
    settings = await effective_settings(session)
    try:
        model = settings.model_for(AITask.EMBEDDING)
        return factory(settings), model
    except (RuntimeError, AINotConfiguredError):
        return None


async def reindex(session: AsyncSession, factory: EmbedderFactory, limit: int = 200) -> int:
    """Gera vetores dos produtos novos/alterados (ou de outro modelo). Devolve quantos."""
    ready = await setup(session, factory)
    if ready is None:
        return 0
    embedder, model = ready
    niches = {n.slug: n.name for n in (await session.scalars(select(Niche))).all()}
    current = {e.product_id: e for e in (await session.scalars(select(ProductEmbedding))).all()}
    todo: list[tuple[Product, str, str]] = []
    for product in (await session.scalars(select(Product).order_by(Product.id))).all():
        text = product_text(product, niches.get(product.niche))
        digest = content_hash(f"{model}\n{text}")
        old = current.get(product.id)
        if old is None or old.content_hash != digest:
            todo.append((product, text, digest))
        if len(todo) >= limit:
            break
    if not todo:
        return 0
    vectors = await embedder.embed([t for _, t, _ in todo], model=model)
    for (product, _, digest), vector in zip(todo, vectors, strict=True):
        row = current.get(product.id)
        if row is None:
            session.add(
                ProductEmbedding(
                    product_id=product.id, model=model, content_hash=digest, embedding=vector
                )
            )
        else:
            row.model, row.content_hash, row.embedding = model, digest, vector
    await session.commit()
    return len(todo)


async def index_status(session: AsyncSession, factory: EmbedderFactory) -> dict[str, Any]:
    ready = await setup(session, factory)
    total = await session.scalar(select(func.count()).select_from(Product)) or 0
    model = ready[1] if ready else None
    indexed = (
        await session.scalar(
            select(func.count())
            .select_from(ProductEmbedding)
            .where(ProductEmbedding.model == model)
        )
        if model
        else 0
    )
    return {"enabled": ready is not None, "model": model, "products": total, "indexed": indexed}


async def _query_vector(embedder: EmbeddingProvider, model: str, q: str) -> list[float]:
    key = (model, " ".join(q.lower().split()))
    if key in _QUERY_CACHE:
        _QUERY_CACHE.move_to_end(key)
        return _QUERY_CACHE[key]
    vector = (await embedder.embed([key[1]], model=model))[0]
    _QUERY_CACHE[key] = vector
    if len(_QUERY_CACHE) > _CACHE_MAX:
        _QUERY_CACHE.popitem(last=False)
    return vector


async def semantic_hits(
    session: AsyncSession,
    factory: EmbedderFactory,
    q: str,
    *,
    max_distance: float,
    niche: str | None = None,
    limit: int = 24,
) -> list[tuple[int, float]] | None:
    """[(product_id, distância)] dos produtos à venda mais próximos; None = indisponível."""
    ready = await setup(session, factory)
    if ready is None:
        return None
    embedder, model = ready
    try:
        vector = await _query_vector(embedder, model, q)
    except Exception:  # fornecedor fora do ar: a loja cai na busca por palavras
        log.warning("busca semântica indisponível", exc_info=True)
        return None
    distance = ProductEmbedding.embedding.cosine_distance(vector).label("d")
    stmt = (
        select(Product.id, distance)
        .join(ProductEmbedding, ProductEmbedding.product_id == Product.id)
        .where(
            ProductEmbedding.model == model,
            Product.status == "ativo",
            Product.guardian_status == "aprovado",
            distance <= max_distance,
        )
        .order_by(distance)
        .limit(limit)
    )
    if niche:
        stmt = stmt.where(Product.niche == niche)
    return [(pid, float(d)) for pid, d in (await session.execute(stmt)).all()]


async def run_indexer(
    factory: async_sessionmaker[AsyncSession], embedder_factory: EmbedderFactory, interval: float
) -> None:
    """Mantém os vetores em dia (produto novo/editado entra na busca em minutos)."""
    while True:
        try:
            async with factory() as session:
                done = await reindex(session, embedder_factory)
                if done:
                    log.info("busca: produtos indexados", extra={"n": done})
        except Exception:
            log.exception("falha no indexador da busca")
        await asyncio.sleep(interval)


def merge_ranked(literal: Sequence[int], semantic: Sequence[int]) -> list[int]:
    """Palavra exata primeiro; depois os parecidos por significado, sem repetir."""
    out = list(dict.fromkeys(literal))
    seen = set(out)
    for pid in semantic:
        if pid not in seen:
            seen.add(pid)
            out.append(pid)
    return out
