"""Contrato de notificação (cliente: API oficial da Meta; operação: gateway MayaSec)."""

from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class Button(BaseModel):
    id: str
    title: str  # ex.: "Aprovar", "Pedir ajuste"


class OutboundMessage(BaseModel):
    to: str  # E.164
    body: str
    template: str | None = None  # obrigatório fora da janela de 24h
    template_params: list[str] = []
    media_url: str | None = None
    buttons: list[Button] = []


@runtime_checkable
class NotifyProvider(Protocol):
    async def send(self, message: OutboundMessage) -> str:
        """Envia e devolve o id da mensagem no provedor."""
        ...
