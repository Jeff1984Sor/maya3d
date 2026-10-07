from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_ai import AINotConfiguredError, AIOutputError, AIRefusedError
from print3d_api.db.session import get_session
from print3d_api.models import AIConfig
from print3d_api.models.ai import AI_CONFIG_ID
from print3d_api.services import ai, audit
from print3d_api.services.guardian import UnknownNicheError

router = APIRouter(prefix="/ai", tags=["admin: IA"])
Session = Annotated[AsyncSession, Depends(get_session)]


def get_ai_factory(request: Request) -> ai.ProviderFactory:
    factory: ai.ProviderFactory = getattr(request.app.state, "ai_factory", ai.default_factory)
    return factory


Factory = Annotated[ai.ProviderFactory, Depends(get_ai_factory)]


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


@router.post("/enrich-product", response_model=ai.EnrichResult)
async def enrich_product(payload: EnrichIn, session: Session, factory: Factory) -> ai.EnrichResult:
    """✨ Poucas palavras → sugestão completa (só sugestão: o painel mostra e o dono aceita)."""
    try:
        return await ai.enrich(
            session, factory, hint=payload.hint, niche_slug=payload.niche, category=payload.category
        )
    except AINotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except RuntimeError as exc:  # modelo não escolhido
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"{exc}: escolha o modelo no painel (IA)"
        ) from exc
    except (AIRefusedError, UnknownNicheError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except AIOutputError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    except ai.PROVIDER_ERRORS as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"o fornecedor de IA recusou a chamada: {exc}"
        ) from exc
