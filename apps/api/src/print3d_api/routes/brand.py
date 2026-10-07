from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.db.session import get_session
from print3d_api.deps import get_brand_service
from print3d_api.schemas.brand import BrandPublic
from print3d_api.services.brand import BrandNotConfiguredError, BrandService

router = APIRouter(prefix="/v1/brand", tags=["brand"])


@router.get("", response_model=BrandPublic)
async def get_brand(
    service: Annotated[BrandService, Depends(get_brand_service)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> BrandPublic:
    """Identidade pública da loja: storefront, admin, e-mails e apps leem daqui."""
    try:
        return await service.get_public(session)
    except BrandNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
