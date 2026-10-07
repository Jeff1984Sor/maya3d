"""Tela Integrações: o dono cola chaves (IA, WhatsApp) no painel em vez do .env."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.db.session import get_session
from print3d_api.services import integrations, notifications, whatsapp
from print3d_notify.meta import MetaWhatsAppProvider

router = APIRouter(prefix="/integrations", tags=["admin: integrações"])
Session = Annotated[AsyncSession, Depends(get_session)]


class IntegrationsIn(BaseModel):
    values: dict[str, str | None] = {}
    clear: list[str] = Field(default_factory=list)


def _http(exc: integrations.IntegrationError) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


@router.get("")
async def get_integrations(session: Session) -> list[dict[str, Any]]:
    """Nunca devolve segredo: só se está configurado, de onde vem e os 4 últimos caracteres."""
    return await integrations.view(session)


@router.put("")
async def put_integrations(payload: IntegrationsIn, session: Session) -> list[dict[str, Any]]:
    try:
        await integrations.save(session, payload.values, payload.clear)
    except integrations.IntegrationError as exc:
        raise _http(exc) from exc
    return await integrations.view(session)


@router.post("/{key}/generate")
async def generate_value(key: str, session: Session) -> dict[str, str]:
    try:
        return {"key": key, "value": await integrations.generate(session, key)}
    except integrations.IntegrationError as exc:
        raise _http(exc) from exc


@router.post("/whatsapp/test")
async def whatsapp_test(request: Request, session: Session) -> dict[str, Any]:
    """Manda uma mensagem de teste para o WhatsApp do dono (Operação) e diz o resultado."""
    wa = await integrations.whatsapp_settings(session, request.app.state.whatsapp)
    if not wa.configured:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "preencha token, ID do número e versão da Graph API"
        )
    note = await notifications.notify_owner(
        session, "teste_whatsapp", "Teste do painel: o WhatsApp da loja está conectado ✅"
    )
    if note.status != "pendente":
        await session.commit()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "cadastre o seu WhatsApp em Operação para receber o teste"
        )
    await session.commit()
    await whatsapp.dispatch_pending(session, MetaWhatsAppProvider(wa), limit=50)
    await session.refresh(note)
    return {"status": note.status, "error": note.last_error}
