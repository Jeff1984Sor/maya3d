"""API pública da loja (sem token de admin). Só expõe o que o cliente pode ver."""

import asyncio
import logging
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from arq.connections import ArqRedis
from arq.jobs import Job, JobStatus
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_ai import AINotConfiguredError, AIOutputError, AIRefusedError
from print3d_ai.prompts import shop_assistant
from print3d_api.db.session import get_session
from print3d_api.deps import get_ai_factory, get_embedder_factory, get_queue, get_storage
from print3d_api.models import Design, OpsConfig, Product, StorePage, Variant
from print3d_api.models.orders import OPS_CONFIG_ID
from print3d_api.schemas.governance import GuardianCheckIn
from print3d_api.schemas.store import (
    CartIn,
    CartOut,
    CheckoutIn,
    CheckoutOut,
    PublicOrder,
    ShippingIn,
    ShippingQuote,
    StoreNiche,
    StoreProduct,
    StoreProductCard,
)
from print3d_api.services import (
    ai,
    assistant,
    content,
    guardian,
    integrations,
    media,
    search,
    store,
)
from print3d_api.services.cep import CepError, CepProvider, ViaCepProvider
from print3d_channels.shipping import ShippingQuoter
from print3d_core.storage import LocalStorage, StorageError
from print3d_mesh.parametric import MODELS
from print3d_mesh.preview import make_preview

router = APIRouter(prefix="/v1/store", tags=["loja"])
Session = Annotated[AsyncSession, Depends(get_session)]
Queue = Annotated[ArqRedis, Depends(get_queue)]
AIFactory = Annotated[ai.ProviderFactory, Depends(get_ai_factory)]
Embedders = Annotated[search.EmbedderFactory, Depends(get_embedder_factory)]
log = logging.getLogger("print3d.store")
ASSISTANT_ERRORS: tuple[type[Exception], ...] = (AIOutputError, AIRefusedError, *ai.PROVIDER_ERRORS)
PREVIEWS_PER_MINUTE = 20  # proteção do worker: prévias 3D são CPU pesado


def get_cep_provider(request: Request) -> CepProvider:
    provider: CepProvider | None = getattr(request.app.state, "cep_provider", None)
    if provider is None:
        provider = ViaCepProvider()
        request.app.state.cep_provider = provider
    return provider


Cep = Annotated[CepProvider, Depends(get_cep_provider)]


async def get_shipping_quoter(request: Request, session: Session) -> ShippingQuoter | None:
    """Melhor Envio configurado em Integrações (trocável nos testes por app.state)."""
    override = getattr(request.app.state, "shipping_quoter", None)
    return override if override is not None else await integrations.shipping_quoter(session)


Quoter = Annotated[ShippingQuoter | None, Depends(get_shipping_quoter)]


def _http(exc: store.StoreError) -> HTTPException:
    code = status.HTTP_404_NOT_FOUND if exc.not_found else status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(code, str(exc))


@router.get("/niches", response_model=list[StoreNiche])
async def niches(session: Session) -> list[StoreNiche]:
    return await store.list_niches(session)


@router.get("/products", response_model=list[StoreProductCard])
async def products(
    request: Request,
    session: Session,
    embedders: Embedders,
    niche: str | None = None,
    q: Annotated[str | None, Query(max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=60)] = 24,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[StoreProductCard]:
    semantic: list[int] | None = None
    if q and len(q.strip()) >= 3 and offset == 0:
        hits = await search.semantic_hits(
            session,
            embedders,
            q,
            max_distance=request.app.state.settings.semantic_max_distance,
            niche=niche,
            limit=limit,
        )
        semantic = [pid for pid, _ in hits] if hits else None
    return await store.list_products(
        session, niche=niche, q=q, limit=limit, offset=offset, semantic_ids=semantic
    )


@router.get("/products/{slug}", response_model=StoreProduct)
async def product(slug: str, session: Session) -> StoreProduct:
    try:
        return await store.product_detail(session, slug)
    except store.StoreError as exc:
        raise _http(exc) from exc


@router.post("/cart", response_model=CartOut, status_code=201)
async def new_cart(session: Session) -> CartOut:
    token = await store.create_cart(session)
    return await store.cart_view(session, token)


@router.get("/cart/{token}", response_model=CartOut)
async def get_cart(token: str, session: Session) -> CartOut:
    try:
        return await store.cart_view(session, token)
    except store.StoreError as exc:
        raise _http(exc) from exc


@router.put("/cart/{token}", response_model=CartOut)
async def put_cart(token: str, payload: CartIn, session: Session) -> CartOut:
    try:
        return await store.set_cart(session, token, payload)
    except store.StoreError as exc:
        await session.rollback()
        raise _http(exc) from exc


@router.post("/shipping", response_model=ShippingQuote)
async def shipping(
    payload: ShippingIn, session: Session, cep: Cep, quoter: Quoter
) -> ShippingQuote:
    try:
        return await store.quote_shipping(
            session,
            cep,
            payload.cep,
            payload.subtotal,
            cart_token=payload.cart_token,
            quoter=quoter,
        )
    except CepError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.post("/checkout", response_model=CheckoutOut, status_code=201)
async def checkout(payload: CheckoutIn, session: Session, cep: Cep, quoter: Quoter) -> CheckoutOut:
    try:
        return await store.checkout(session, cep, payload, quoter)
    except store.StoreError as exc:
        await session.rollback()
        raise _http(exc) from exc
    except CepError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.get("/orders/{token}", response_model=PublicOrder)
async def order(token: str, session: Session) -> PublicOrder:
    try:
        return await store.public_order(session, token)
    except store.StoreError as exc:
        raise _http(exc) from exc


# --- Personalizador 3D (prévia) ---------------------------------------------------------------
class ModelOut(BaseModel):
    slug: str
    title: str
    params_schema: dict[str, Any]


class PreviewJob(BaseModel):
    job_id: str


@router.get("/parametric/{slug}", response_model=ModelOut)
async def parametric_model(slug: str) -> ModelOut:
    model = MODELS.get(slug)
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "modelo não existe")
    return ModelOut(
        slug=model.slug, title=model.title, params_schema=model.params_model.model_json_schema()
    )


@router.post("/parametric/{slug}/preview", response_model=PreviewJob, status_code=202)
async def preview(
    slug: str, params: Annotated[dict[str, Any], Body()], session: Session, queue: Queue
) -> PreviewJob:
    model = MODELS.get(slug)
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "modelo não existe")
    try:
        parsed = model.parse(params)
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, exc.errors(include_url=False)
        ) from exc
    texts = [str(v) for k in model.text_fields if (v := getattr(parsed, k, None))]
    if texts:
        decision = await guardian.decide(
            session,
            GuardianCheckIn(
                niche=model.niche, title=model.title, origin="parametrico", customer_text=texts
            ),
        )
        if not decision.approved:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "texto não permitido: " + "; ".join(v.message for v in decision.violations),
            )
    bucket = "print3d:store:previews"
    used = await queue.incr(bucket)
    if used == 1:
        await queue.expire(bucket, 60)
    if used > PREVIEWS_PER_MINUTE:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "muitas prévias agora; tente em 1 minuto"
        )
    job = await queue.enqueue_job("generate_parametric", slug, parsed.model_dump())
    if job is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "prévia duplicada")
    return PreviewJob(job_id=job.job_id)


@router.get("/jobs/{job_id}")
async def preview_state(job_id: str, queue: Queue) -> dict[str, Any]:
    """Estado de uma prévia. Só devolve o necessário para o visualizador."""
    job = Job(job_id, redis=queue)
    state = await job.status()
    if state != JobStatus.complete:
        return {"status": "processando" if state != JobStatus.not_found else "desconhecido"}
    info = await job.result_info()
    if info is None or not info.success or not isinstance(info.result, dict):
        return {"status": "falhou"}
    result = info.result
    if not str(result.get("prefix", "")).startswith("parametric/"):
        return {"status": "desconhecido"}
    return {
        "status": "concluido",
        "prefix": result["prefix"],
        "combined": result.get("combined"),
        "bbox_mm": result.get("bbox_mm"),
        "printable": result.get("printable"),
        "issues": result.get("issues", []),
    }


@router.get("/files/parametric/{job_id}/{name}")
async def preview_file(
    job_id: str, name: str, storage: Annotated[LocalStorage, Depends(get_storage)]
) -> FileResponse:
    if not name.endswith(".stl"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "arquivo não existe")
    try:
        path = storage.local_path(f"parametric/{job_id}/{name}")
    except StorageError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "arquivo não existe")
    return FileResponse(path, media_type="model/stl")


class StoreSettings(BaseModel):
    free_shipping_min: Decimal | None
    local_cities_ibge: list[str]
    pickup_enabled: bool
    pix_enabled: bool
    assistant_enabled: bool = False


@router.get("/settings", response_model=StoreSettings)
async def store_settings(session: Session) -> StoreSettings:
    """O que a vitrine precisa para a faixa de frete grátis e o checkout."""
    ops = await session.get(OpsConfig, OPS_CONFIG_ID)
    return StoreSettings(
        free_shipping_min=ops.local_free_shipping_min if ops else None,
        local_cities_ibge=list(ops.local_cities_ibge) if ops else [],
        pickup_enabled=bool(ops and ops.pickup_enabled),
        pix_enabled=bool(ops and ops.pix_key),
        assistant_enabled=bool(
            await assistant.model_for(session) and await assistant.has_catalog(session)
        ),
    )


class AssistantIn(BaseModel):
    messages: list[shop_assistant.ChatTurn] = Field(min_length=1, max_length=16)
    client_id: str | None = Field(default=None, max_length=64)  # IP/visitante, vindo da vitrine


async def _assistant_quota(queue: ArqRedis, settings: Any, client: str) -> None:
    """Proteção de custo: por visitante/minuto e total do dia."""
    day = f"print3d:store:assistant:day:{date.today().isoformat()}"
    per_client = f"print3d:store:assistant:min:{client}"
    used_day = await queue.incr(day)
    if used_day == 1:
        await queue.expire(day, 86_400)
    used_min = await queue.incr(per_client)
    if used_min == 1:
        await queue.expire(per_client, 60)
    if used_day > settings.assistant_daily_limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "assistente em pausa hoje")
    if used_min > settings.assistant_per_minute:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "muitas mensagens; espere um minutinho"
        )


@router.post("/assistant", response_model=assistant.AssistantOut)
async def ask_assistant(
    payload: AssistantIn,
    request: Request,
    session: Session,
    queue: Queue,
    factory: AIFactory,
    embedders: Embedders,
) -> assistant.AssistantOut:
    if payload.messages[-1].role != "user":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "a última mensagem é do cliente")
    settings = request.app.state.settings
    client = payload.client_id or (request.client.host if request.client else "anon")
    await _assistant_quota(queue, settings, client)
    try:
        return await assistant.ask(
            session,
            factory,
            embedders,
            payload.messages,
            max_distance=settings.semantic_max_distance,
        )
    except AINotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "assistente desligado") from exc
    except ASSISTANT_ERRORS as exc:
        log.warning("assistente falhou", exc_info=True)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "o assistente não conseguiu responder agora"
        ) from exc


# --- Conteúdo (CMS) -------------------------------------------------------------------------
@router.get("/home", response_model=content.HomeOut)
async def home(session: Session) -> content.HomeOut:
    return await content.home(session)


class PageLink(BaseModel):
    slug: str
    title: str


class PageOut(PageLink):
    body: str


@router.get("/pages", response_model=list[PageLink])
async def footer_pages(session: Session) -> list[PageLink]:
    return [
        PageLink(slug=p.slug, title=p.title)
        for p in await content.pages(session, only_published=True)
        if p.in_footer
    ]


@router.get("/pages/{slug}", response_model=PageOut)
async def page(slug: str, session: Session) -> PageOut:
    found = await session.get(StorePage, slug)
    if found is None or not found.published:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "página não encontrada")
    return PageOut(slug=found.slug, title=found.title, body=found.body)


@router.get("/media/{key:path}")
async def media_file(
    key: str, storage: Annotated[LocalStorage, Depends(get_storage)]
) -> FileResponse:
    """Imagens públicas da loja. Só o prefixo media/ (fotos, logo, destaque) e só WebP."""
    if not key.startswith(f"{media.PREFIX}/") or not key.endswith(".webp"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "não encontrado")
    try:
        path = storage.local_path(key)
    except StorageError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "não encontrado") from exc
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "não encontrado")
    return FileResponse(
        path,
        media_type="image/webp",
        headers={"cache-control": "public, max-age=31536000, immutable"},  # nome é único
    )


# --- Prévia 3D (girar e trocar de cor na página do produto) ---------------------------------
_preview_locks: dict[int, asyncio.Lock] = {}


@router.get("/products/{slug}/preview.stl")
async def product_preview(
    slug: str, session: Session, storage: Annotated[LocalStorage, Depends(get_storage)]
) -> FileResponse:
    """Malha leve (só para ver), gerada uma vez por produto e guardada."""
    try:
        detail = await store.product_detail(session, slug)
    except store.StoreError as exc:
        raise _http(exc) from exc
    product = await session.scalar(select(Product).where(Product.slug == slug))
    design = await session.get(Design, product.design_id) if product else None
    source = (design.source_file_url if design else None) or ""
    if not product or not detail.model3d or not source.startswith("library/"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "produto sem prévia 3D")
    out = storage.local_path(f"previews/{product.id}.stl")
    if not out.is_file():
        variant = await session.scalar(
            select(Variant).where(Variant.product_id == product.id).order_by(Variant.id)
        )
        height = (variant.params or {}).get("altura_mm") if variant else None
        if not height and variant and variant.dims_mm:
            height = max(variant.dims_mm)
        lock = _preview_locks.setdefault(product.id, asyncio.Lock())
        async with lock:
            if not out.is_file():
                try:
                    await asyncio.to_thread(
                        make_preview, storage.local_path(source), out, height_mm=height
                    )
                except (OSError, ValueError, StorageError) as exc:
                    raise HTTPException(
                        status.HTTP_404_NOT_FOUND, "prévia 3D indisponível"
                    ) from exc
    return FileResponse(
        out, media_type="model/stl", headers={"cache-control": "public, max-age=86400"}
    )
