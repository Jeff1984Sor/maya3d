from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.db.session import get_session
from print3d_api.schemas.pricing import QuoteRequest, QuoteResponse
from print3d_api.services import pricing

router = APIRouter(prefix="/pricing", tags=["admin: preços"])


@router.post("/quote", response_model=QuoteResponse)
async def quote(
    payload: QuoteRequest, session: Annotated[AsyncSession, Depends(get_session)]
) -> QuoteResponse:
    """Custo detalhado + preço e lucro líquido em cada canal com tarifa cadastrada."""
    try:
        return await pricing.quote(session, payload)
    except pricing.QuoteInputError as exc:
        code = status.HTTP_404_NOT_FOUND if exc.not_found else status.HTTP_422_UNPROCESSABLE_ENTITY
        raise HTTPException(code, str(exc)) from exc
