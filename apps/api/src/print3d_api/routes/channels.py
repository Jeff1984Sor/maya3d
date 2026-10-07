"""Retorno de autorização dos marketplaces (o navegador do dono volta para cá)."""

from html import escape
from typing import Annotated

from arq.connections import ArqRedis
from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.db.session import get_session
from print3d_api.deps import get_queue
from print3d_api.services import mercadolivre as ml
from print3d_channels.mercadolivre import MercadoLivreError

router = APIRouter(prefix="/v1/channels", tags=["canais"])


def _page(title: str, text: str, status: int = 200) -> HTMLResponse:
    body = (
        "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'>"
        f"<title>{escape(title)}</title><body style='font-family:system-ui;padding:40px'>"
        f"<h2>{escape(title)}</h2><p>{escape(text)}</p></body>"
    )
    return HTMLResponse(body, status_code=status)


@router.get("/mercadolivre/callback", response_class=HTMLResponse)
async def ml_callback(
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[ArqRedis, Depends(get_queue)],
    code: Annotated[str | None, Query(max_length=200)] = None,
    state: Annotated[str | None, Query(max_length=100)] = None,
    error: Annotated[str | None, Query(max_length=200)] = None,
) -> HTMLResponse:
    if error or not code or not state:
        return _page("Conexão cancelada", "Volte ao painel e tente de novo.", 400)
    try:
        nickname = await ml.finish_connect(session, redis, code, state)
    except (ml.MLError, MercadoLivreError) as exc:
        return _page("Não deu para conectar", str(exc), 400)
    return _page("Mercado Livre conectado ✅", f"Conta {nickname}. Pode fechar esta aba.")
