"""Webhooks de terceiros. WhatsApp (Meta): handshake GET e eventos POST assinados.

A Meta só aceita URL HTTPS: este endpoint fica pronto e é registrado quando houver domínio.
"""

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.db.session import get_session
from print3d_api.services import whatsapp
from print3d_notify.meta import WhatsAppSettings, parse_webhook, verify_signature

log = logging.getLogger("print3d.webhooks")
router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])
Session = Annotated[AsyncSession, Depends(get_session)]


def get_whatsapp_settings(request: Request) -> WhatsAppSettings:
    settings: WhatsAppSettings = request.app.state.whatsapp
    return settings


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
