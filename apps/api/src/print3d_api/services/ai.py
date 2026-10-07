"""IA no sistema: configuração (env + painel), status e ✨ Enriquecer produto.

A IA só sugere. Nada é gravado sem o dono aceitar; a sugestão passa pelo Guardião antes.
"""

from collections.abc import Callable
from typing import Any

import anthropic
import openai
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_ai import AISettings, AITask
from print3d_ai.factory import ChatProvider, make_provider
from print3d_ai.prompts import enrich_product
from print3d_api.models import AIConfig, BrandSettings, Niche
from print3d_api.models.ai import AI_CONFIG_ID
from print3d_api.models.brand import SINGLETON_ID
from print3d_api.schemas.governance import GuardianCheckIn, ViolationOut
from print3d_api.services import audit, guardian

ProviderFactory = Callable[[AISettings], ChatProvider]
PROVIDER_ERRORS: tuple[type[Exception], ...] = (anthropic.APIError, openai.APIError)


class AIStatus(BaseModel):
    configured: bool
    provider: str
    models: dict[str, str | None]
    available_models: list[str] = []
    error: str | None = None


class EnrichResult(BaseModel):
    suggestion: enrich_product.ProductSuggestion
    guardian_approved: bool
    violations: list[ViolationOut]
    model: str
    prompt_version: str = enrich_product.VERSION


async def effective_settings(session: AsyncSession) -> AISettings:
    """Ambiente (chave, fornecedor) + modelos escolhidos no painel por cima."""
    base = AISettings()
    cfg = await session.get(AIConfig, AI_CONFIG_ID)
    if cfg is None:
        return base
    overrides: dict[str, Any] = {
        f"model_{task.value}": getattr(cfg, f"model_{task.value}")
        for task in AITask
        if getattr(cfg, f"model_{task.value}")
    }
    return base.model_copy(update=overrides)


async def status(session: AsyncSession, factory: ProviderFactory) -> AIStatus:
    settings = await effective_settings(session)
    models = {task.value: getattr(settings, f"model_{task.value}") for task in AITask}
    configured = settings.api_key is not None and bool(settings.api_key.get_secret_value())
    out = AIStatus(configured=configured, provider=settings.provider, models=models)
    if not configured:
        out.error = "chave não configurada no servidor (AI_API_KEY)"
        return out
    try:
        out.available_models = await factory(settings).list_models()
    except Exception as exc:  # chave inválida, rede, fornecedor fora do ar
        out.error = f"não foi possível listar modelos: {type(exc).__name__}"
    return out


async def enrich(
    session: AsyncSession,
    factory: ProviderFactory,
    *,
    hint: str,
    niche_slug: str,
    category: str | None,
) -> EnrichResult:
    settings = await effective_settings(session)
    model = settings.model_for(AITask.DEFAULT)  # RuntimeError se não escolhido
    provider = factory(settings)

    brand = await session.get(BrandSettings, SINGLETON_ID)
    niche = await session.scalar(select(Niche).where(Niche.slug == niche_slug))
    if niche is None:
        raise guardian.UnknownNicheError(f"nicho '{niche_slug}' não existe")
    system, prompt = enrich_product.build(
        loja=brand.name if brand else "a loja",
        voz_marca=(brand.voice or "") if brand else "",
        nicho=niche.name,
        voz_nicho=niche.voice or "",
        dica=hint,
        categoria=category,
    )
    suggestion = await provider.complete_json(
        system=system, prompt=prompt, schema=enrich_product.ProductSuggestion, model=model
    )

    decision = await guardian.decide(
        session,
        GuardianCheckIn(
            niche=niche_slug,
            title=suggestion.title,
            description="\n".join([suggestion.description, *suggestion.bullets]),
            tags=suggestion.tags,
            occasions=suggestion.occasions,
            category=suggestion.category,
            origin="parametrico",
        ),
    )
    await audit.record(
        session,
        actor="ia",
        action="sugestao_produto",
        decision=decision.verdict,
        reason=decision.reason,
        payload={"dica": hint, "nicho": niche_slug, "modelo": model, "titulo": suggestion.title},
    )
    await session.commit()
    return EnrichResult(
        suggestion=suggestion,
        guardian_approved=decision.approved,
        violations=[
            ViolationOut(code=v.code, message=v.message, evidence=v.evidence)
            for v in decision.violations
        ],
        model=model,
    )


def default_factory(settings: AISettings) -> ChatProvider:
    return make_provider(settings)
