from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.db.session import get_session
from print3d_api.models.pricing import COST_CONFIG_ID, CostConfig
from print3d_api.schemas.admin import CostConfigIn, CostConfigOut

router = APIRouter(prefix="/cost-config", tags=["admin: custos"])
Session = Annotated[AsyncSession, Depends(get_session)]


async def _load(session: AsyncSession) -> CostConfig:
    config = await session.get(CostConfig, COST_CONFIG_ID)
    if config is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "cost_config ausente (migrações)")
    return config


@router.get("", response_model=CostConfigOut)
async def get_cost_config(session: Session) -> CostConfig:
    return await _load(session)


@router.put("", response_model=CostConfigOut)
async def put_cost_config(payload: CostConfigIn, session: Session) -> CostConfig:
    """Mudar custos muda preços: a Fase 3 dispara a ressincronização dos anúncios a partir daqui."""
    config = await _load(session)
    data = payload.model_dump()
    data["margin_by_category"] = {k: str(v) for k, v in payload.margin_by_category.items()}
    for field, value in data.items():
        setattr(config, field, value)
    await session.commit()
    await session.refresh(config)
    return config
