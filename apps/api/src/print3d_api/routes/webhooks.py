"""Webhooks de terceiros. WhatsApp (Meta): handshake GET e eventos POST assinados.

A Meta só aceita URL HTTPS: este endpoint fica pronto e é registrado quando houver domínio.
"""

import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.db.session import get_session
from print3d_api.services import integrations, mercadolivre, shopee, whatsapp
from print3d_notify.meta import WhatsAppSettings, parse_webhook, verify_signature

log = logging.getLogger("print3d.webhooks")
router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])
Session = Annotated[AsyncSession, Depends(get_session)]


async def get_whatsapp_settings(request: Request, session: Session) -> WhatsAppSettings:
    """Painel Integrações > .env."""
    return await integrations.whatsapp_settings(session, request.app.state.whatsapp)


WA = Annotated[WhatsAppSettings, Depends(get_whatsapp_settings)]


@router.get("/whatsapp", response_class=PlainTextResponse)
async def whatsapp_verify(
    wa: WA,
    mode: Annotated[str | None, Query(alias="hub.mode")] = None,
    token: Annotated[str | None, Query(alias="hub.verify_token")] = None,
    challenge: Annotated[str | None, Query(alias="hub.challenge")] = None,
) -> str:
    expected = wa.verify_token.get_secret_value() if wa.verify_token else None
    if mode != "subscribe" or not expected or token != expected or challenge is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "verificação recusada")
    return challenge


@router.post("/whatsapp")
async def whatsapp_events(request: Request, session: Session, wa: WA) -> dict[str, int]:
    if not wa.app_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "WHATSAPP_APP_SECRET ausente")
    raw = await request.body()  # assinatura é sobre os bytes crus
    if not verify_signature(
        raw, request.headers.get("x-hub-signature-256"), wa.app_secret.get_secret_value()
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "assinatura inválida")
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "json inválido") from exc
    handled = 0
    for msg in parse_webhook(payload):
        try:
            await whatsapp.handle_inbound(session, msg)
            handled += 1
        except Exception:  # uma mensagem ruim não derruba as outras; a Meta reenviaria tudo
            await session.rollback()
            log.exception("falha ao tratar mensagem", extra={"wamid": msg.message_id})
    # respostas saem na hora (sem esperar o ciclo do despachante)
    kick = getattr(request.app.state, "dispatch_now", None)
    if handled and kick is not None:
        kick.set()
    return {"received": handled}


async def _ml_process(app_state: Any, payload: dict[str, Any]) -> None:
    async with app_state.session_factory() as session:
        try:
            result = await mercadolivre.handle_notification(session, payload)
            log.info("notificação ML", extra={"topico": payload.get("topic"), "resultado": result})
        except Exception:
            await session.rollback()
            log.exception("falha ao tratar notificação do ML")


@router.post("/mercadolivre")
async def mercadolivre_events(request: Request, background: BackgroundTasks) -> dict[str, str]:
    """O ML exige resposta 200 rápida; o trabalho (ler pedido/pergunta na API do ML com o
    nosso token) acontece depois."""
    try:
        payload = await request.json()
    except ValueError:
        return {"status": "ignorada"}
    if isinstance(payload, dict) and payload.get("topic") and payload.get("resource"):
        background.add_task(_ml_process, request.app.state, payload)
    return {"status": "recebida"}


async def _shopee_process(app_state: Any, payload: dict[str, Any]) -> None:
    async with app_state.session_factory() as session:
        try:
            result = await shopee.handle_push(session, payload)
            log.info("push Shopee", extra={"codigo": payload.get("code"), "resultado": result})
        except Exception:
            await session.rollback()
            log.exception("falha ao tratar push da Shopee")


@router.post("/shopee")
async def shopee_events(
    request: Request, background: BackgroundTasks, session: Session
) -> dict[str, str]:
    """Push assinado (Authorization = HMAC da URL + corpo). Resposta rápida; trabalho depois."""
    raw = await request.body()
    if not await shopee.verify(session, raw, request.headers.get("authorization")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "assinatura inválida")
    try:
        payload = json.loads(raw)
    except ValueError:
        return {"status": "ignorada"}
    if isinstance(payload, dict):
        background.add_task(_shopee_process, request.app.state, payload)
    return {"status": "recebida"}
