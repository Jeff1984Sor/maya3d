import asyncio
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_ai import AINotConfiguredError, AIOutputError, AIRefusedError, AITask, ImageInput
from print3d_ai.prompts import channel_copy
from print3d_ai.prompts import product_from_photo as product_from_photo_prompt
from print3d_api.db.session import get_session
from print3d_api.deps import get_ai_factory, get_embedder_factory, get_storage
from print3d_api.models import AIConfig, BrandSettings, Product
from print3d_api.models.ai import AI_CONFIG_ID
from print3d_api.models.brand import SINGLETON_ID
from print3d_api.services import ai, audit, content, copywriter, search
from print3d_api.services.guardian import UnknownNicheError
from print3d_core.storage import LocalStorage

router = APIRouter(prefix="/ai", tags=["admin: IA"])
Session = Annotated[AsyncSession, Depends(get_session)]


Factory = Annotated[ai.ProviderFactory, Depends(get_ai_factory)]
Embedders = Annotated[search.EmbedderFactory, Depends(get_embedder_factory)]


class AIConfigIn(BaseModel):
    model_default: str | None = Field(default=None, max_length=80)
    model_guardian: str | None = Field(default=None, max_length=80)
    model_personalizer: str | None = Field(default=None, max_length=80)
    model_embedding: str | None = Field(default=None, max_length=80)
    daily_budget_usd: Decimal = Field(default=Decimal(5), ge=0, le=1000)


class EnrichIn(BaseModel):
    hint: str = Field(min_length=3, max_length=500)
    niche: str
    category: str | None = None


@router.get("/status", response_model=ai.AIStatus)
async def ai_status(session: Session, factory: Factory) -> ai.AIStatus:
    return await ai.status(session, factory)


@router.put("/config", response_model=ai.AIStatus)
async def put_config(payload: AIConfigIn, session: Session, factory: Factory) -> ai.AIStatus:
    cfg = await session.get(AIConfig, AI_CONFIG_ID)
    if cfg is None:
        raise HTTPException(503, "ai_config ausente (migrações)")
    for field, value in payload.model_dump().items():
        setattr(cfg, field, value or None if isinstance(value, str) else value)
    await audit.record(
        session,
        actor="admin",
        action="ia_configurada",
        entity_type="ai_config",
        payload=payload.model_dump(mode="json"),
    )
    await session.commit()
    return await ai.status(session, factory)


def _ai_http(exc: Exception) -> HTTPException:
    """Erros de IA → HTTP com mensagem útil para o painel."""
    if isinstance(exc, AINotConfiguredError):
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc))
    if isinstance(exc, RuntimeError):  # modelo não escolhido
        return HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"{exc}: escolha o modelo no painel (IA)"
        )
    if isinstance(exc, AIRefusedError | UnknownNicheError):
        return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    if isinstance(exc, AIOutputError):
        return HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))
    return HTTPException(
        status.HTTP_502_BAD_GATEWAY, f"o fornecedor de IA recusou a chamada: {exc}"
    )


AI_ERRORS: tuple[type[Exception], ...] = (
    AINotConfiguredError,
    RuntimeError,
    AIRefusedError,
    UnknownNicheError,
    AIOutputError,
    *ai.PROVIDER_ERRORS,
)


@router.post("/enrich-product", response_model=ai.EnrichResult)
async def enrich_product(payload: EnrichIn, session: Session, factory: Factory) -> ai.EnrichResult:
    """✨ Poucas palavras → sugestão completa (só sugestão: o painel mostra e o dono aceita)."""
    try:
        return await ai.enrich(
            session, factory, hint=payload.hint, niche_slug=payload.niche, category=payload.category
        )
    except AI_ERRORS as exc:
        raise _ai_http(exc) from exc


# --- ✍️ Redator por canal -------------------------------------------------------------------
class CopyIn(BaseModel):
    product_id: int
    channels: list[Literal["site", "mercadolivre", "shopee", "instagram"]] = Field(min_length=1)


class CopyPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    bullets: list[str] | None = None
    keywords: list[str] | None = None
    hashtags: list[str] | None = None


class CopyStatusIn(BaseModel):
    status: Literal["aprovado", "descartado", "rascunho"]


class CopyOut(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    product_id: int
    channel: str
    title: str
    description: str
    bullets: list[str]
    keywords: list[str]
    hashtags: list[str]
    status: str
    guardian_status: str
    issues: list[str]
    model: str | None
    title_max: int = 0

    @classmethod
    def of(cls, row: Any) -> "CopyOut":
        out = cls.model_validate(row)
        profile = channel_copy.PROFILES.get(row.channel)
        out.title_max = profile.title_max if profile else 0
        return out


def _copy_http(exc: copywriter.CopyError) -> HTTPException:
    code = status.HTTP_404_NOT_FOUND if exc.not_found else status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(code, str(exc))


@router.post("/channel-copy", response_model=list[CopyOut])
async def generate_copy(payload: CopyIn, session: Session, factory: Factory) -> list[CopyOut]:
    """Gera (ou refaz) os textos dos canais pedidos. Ficam como rascunho até o dono aprovar."""
    try:
        rows = await copywriter.generate(session, factory, payload.product_id, payload.channels)
    except copywriter.CopyError as exc:
        raise _copy_http(exc) from exc
    except AI_ERRORS as exc:
        raise _ai_http(exc) from exc
    return [CopyOut.of(r) for r in rows]


@router.get("/channel-copy", response_model=list[CopyOut])
async def list_copy(session: Session, product_id: int) -> list[CopyOut]:
    return [CopyOut.of(r) for r in await copywriter.list_for(session, product_id)]


@router.patch("/channel-copy/{copy_id}", response_model=CopyOut)
async def edit_copy(copy_id: int, payload: CopyPatch, session: Session) -> CopyOut:
    try:
        row = await copywriter.edit(session, copy_id, payload.model_dump(exclude_none=True))
    except copywriter.CopyError as exc:
        raise _copy_http(exc) from exc
    return CopyOut.of(row)


@router.post("/channel-copy/{copy_id}/status", response_model=CopyOut)
async def copy_status(copy_id: int, payload: CopyStatusIn, session: Session) -> CopyOut:
    try:
        row = await copywriter.set_status(session, copy_id, payload.status)
    except copywriter.CopyError as exc:
        raise _copy_http(exc) from exc
    return CopyOut.of(row)


@router.post("/channel-copy/{copy_id}/apply")
async def apply_copy(copy_id: int, session: Session) -> dict[str, Any]:
    """Texto da loja aprovado → produto (o Guardião verifica de novo)."""
    try:
        product = await copywriter.apply_to_product(session, copy_id)
    except copywriter.CopyError as exc:
        raise _copy_http(exc) from exc
    return {"product_id": product.id, "title": product.title, "guardian": product.guardian_status}


# --- 🔎 Busca semântica ----------------------------------------------------------------------
@router.get("/search/status")
async def search_status(session: Session, embedders: Embedders) -> dict[str, Any]:
    return await search.index_status(session, embedders)


@router.post("/search/reindex")
async def search_reindex(session: Session, embedders: Embedders) -> dict[str, Any]:
    """Indexa agora (o indexador automático faz isso a cada poucos minutos)."""
    try:
        done = await search.reindex(session, embedders, limit=1000)
    except AI_ERRORS as exc:
        raise _ai_http(exc) from exc
    return {**await search.index_status(session, embedders), "done": done}


@router.get("/search/test")
async def search_test(
    request: Request,
    session: Session,
    embedders: Embedders,
    q: Annotated[str, Query(min_length=2, max_length=120)],
) -> dict[str, Any]:
    """Testa a busca por significado: o que a loja mostraria e a distância de cada um."""
    settings = request.app.state.settings
    hits = await search.semantic_hits(session, embedders, q, max_distance=2.0, limit=20)
    if hits is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "busca semântica desligada: escolha o modelo de embedding no painel (IA)",
        )
    titles = dict(
        (
            await session.execute(
                select(Product.id, Product.title).where(Product.id.in_([pid for pid, _ in hits]))
            )
        ).all()
    )
    return {
        "max_distance": settings.semantic_max_distance,
        "hits": [
            {
                "product_id": pid,
                "title": titles.get(pid, ""),
                "distance": round(d, 3),
                "shown": d <= settings.semantic_max_distance,
            }
            for pid, d in hits
        ],
    }


# --- 📷 Produto pela foto (visão) -------------------------------------------------------------
@router.post("/products/{product_id}/from-photo")
async def product_from_photo(
    product_id: int,
    session: Session,
    factory: Factory,
    storage: Annotated[LocalStorage, Depends(get_storage)],
) -> dict[str, Any]:
    """A IA olha a capa e diz o tipo da peça + título/descrição. Não grava nada: devolve a
    sugestão e os tamanhos P/M/G da tabela do tipo (medidas nunca vêm da IA)."""
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "produto não existe")
    images = await content.images_of(session, product_id)
    if not images:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "produto sem foto")
    settings = await ai.effective_settings(session)
    try:
        model = settings.model_for(AITask.GUARDIAN)  # modelo com visão (Guardião visual)
        brand = await session.get(BrandSettings, SINGLETON_ID)
        system, prompt = product_from_photo_prompt.build(
            loja=brand.name if brand else "a loja",
            titulo=product.title,
            colecao=product.category,
        )
        data = await asyncio.to_thread(storage.local_path(images[0].key).read_bytes)
        result = await factory(settings).complete_json(
            system=system,
            prompt=prompt,
            schema=product_from_photo_prompt.PhotoProduct,
            model=model,
            max_tokens=1500,
            images=[ImageInput(data, "image/webp")],
        )
    except AI_ERRORS as exc:
        raise _ai_http(exc) from exc
    return {
        **result.model_dump(),
        "sizes_mm": product_from_photo_prompt.SIZES[result.kind],
        "model": model,
        "prompt_version": product_from_photo_prompt.VERSION,
    }
