"""API pública da loja (sem token de admin). Só expõe o que o cliente pode ver."""

from decimal import Decimal
from typing import Annotated, Any

from arq.connections import ArqRedis
from arq.jobs import Job, JobStatus
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.db.session import get_session
from print3d_api.deps import get_queue, get_storage
from print3d_api.models import OpsConfig
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
from print3d_api.services import guardian, store
from print3d_api.services.cep import CepError, CepProvider, ViaCepProvider
from print3d_core.storage import LocalStorage, StorageError
from print3d_mesh.parametric import MODELS

router = APIRouter(prefix="/v1/store", tags=["loja"])
Session = Annotated[AsyncSession, Depends(get_session)]
Queue = Annotated[ArqRedis, Depends(get_queue)]
PREVIEWS_PER_MINUTE = 20  # proteção do worker: prévias 3D são CPU pesado


def get_cep_provider(request: Request) -> CepProvider:
    provider: CepProvider | None = getattr(request.app.state, "cep_provider", None)
    if provider is None:
        provider = ViaCepProvider()
        request.app.state.cep_provider = provider
    return provider


Cep = Annotated[CepProvider, Depends(get_cep_provider)]


def _http(exc: store.StoreError) -> HTTPException:
    code = status.HTTP_404_NOT_FOUND if exc.not_found else status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(code, str(exc))


@router.get("/niches", response_model=list[StoreNiche])
async def niches(session: Session) -> list[StoreNiche]:
    return await store.list_niches(session)


@router.get("/products", response_model=list[StoreProductCard])
async def products(
    session: Session,
    niche: str | None = None,
    q: Annotated[str | None, Query(max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=60)] = 24,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[StoreProductCard]:
    return await store.list_products(session, niche=niche, q=q, limit=limit, offset=offset)


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
async def shipping(payload: ShippingIn, session: Session, cep: Cep) -> ShippingQuote:
    try:
        return await store.quote_shipping(session, cep, payload.cep, payload.subtotal)
    except CepError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.post("/checkout", response_model=CheckoutOut, status_code=201)
async def checkout(payload: CheckoutIn, session: Session, cep: Cep) -> CheckoutOut:
    try:
        return await store.checkout(session, cep, payload)
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
    texts = [str(v) for k in ("letter", "name", "lid_text") if (v := getattr(parsed, k, None))]
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


@router.get("/settings", response_model=StoreSettings)
async def store_settings(session: Session) -> StoreSettings:
    """O que a vitrine precisa para a faixa de frete grátis e o checkout."""
    ops = await session.get(OpsConfig, OPS_CONFIG_ID)
    return StoreSettings(
        free_shipping_min=ops.local_free_shipping_min if ops else None,
        local_cities_ibge=list(ops.local_cities_ibge) if ops else [],
        pickup_enabled=bool(ops and ops.pickup_enabled),
        pix_enabled=bool(ops and ops.pix_key),
    )
