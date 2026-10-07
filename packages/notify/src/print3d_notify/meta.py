"""WhatsApp Cloud API (Meta). Envio de texto, imagem e botões; fallback para template aprovado
quando a janela de 24 h está fechada; verificação de assinatura e leitura do webhook.

Tudo configurável por ambiente (WHATSAPP_*): versão da Graph API, token, número, template.
"""

import hashlib
import hmac
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from print3d_notify.provider import OutboundMessage

# Erro da Meta para mensagem livre fora da janela de 24 h (exige template).
REENGAGEMENT_ERROR = 131047


class WhatsAppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="WHATSAPP_", extra="ignore")

    token: SecretStr | None = None
    phone_number_id: str | None = None
    graph_version: str | None = None  # ex.: v23.0 — conferir na documentação da Meta
    app_secret: SecretStr | None = None  # assinatura do webhook
    verify_token: SecretStr | None = None  # handshake do webhook
    template_status: str | None = None  # template aprovado com 1 variável (o texto)
    template_lang: str = "pt_BR"

    @property
    def configured(self) -> bool:
        return bool(self.token and self.phone_number_id and self.graph_version)


class WhatsAppError(Exception):
    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


def _digits(number: str) -> str:
    return "".join(c for c in number if c.isdigit())


def build_payload(message: OutboundMessage) -> dict[str, Any]:
    """Mensagem livre: botões (interativa), imagem com legenda ou texto."""
    base: dict[str, Any] = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": _digits(message.to),
    }
    if message.buttons:
        interactive: dict[str, Any] = {
            "type": "button",
            "body": {"text": message.body[:1024]},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b.id[:256], "title": b.title[:20]}}
                    for b in message.buttons[:3]
                ]
            },
        }
        if message.media_url:
            interactive["header"] = {"type": "image", "image": {"link": message.media_url}}
        return {**base, "type": "interactive", "interactive": interactive}
    if message.media_url:
        return {
            **base,
            "type": "image",
            "image": {"link": message.media_url, "caption": message.body[:1024]},
        }
    return {**base, "type": "text", "text": {"body": message.body[:4096], "preview_url": False}}


def build_template_payload(message: OutboundMessage, template: str, lang: str) -> dict[str, Any]:
    text = " ".join(message.body.split())[:1000]  # parâmetro de template não aceita quebra de linha
    return {
        "messaging_product": "whatsapp",
        "to": _digits(message.to),
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": lang},
            "components": [{"type": "body", "parameters": [{"type": "text", "text": text}]}],
        },
    }


class MetaWhatsAppProvider:
    def __init__(self, settings: WhatsAppSettings, client: httpx.AsyncClient | None = None) -> None:
        if not settings.configured:
            raise WhatsAppError(
                "WhatsApp não configurado (WHATSAPP_TOKEN, _PHONE_NUMBER_ID, _GRAPH_VERSION)"
            )
        self._s = settings
        self._client = client

    @property
    def _url(self) -> str:
        return (
            f"https://graph.facebook.com/{self._s.graph_version}/{self._s.phone_number_id}/messages"
        )

    async def _post(self, payload: dict[str, Any]) -> str:
        assert self._s.token is not None
        headers = {"Authorization": f"Bearer {self._s.token.get_secret_value()}"}
        client = self._client or httpx.AsyncClient(timeout=15)
        try:
            res = await client.post(self._url, json=payload, headers=headers)
        finally:
            if self._client is None:
                await client.aclose()
        data = res.json() if res.content else {}
        if res.status_code >= 400:
            err = data.get("error", {}) if isinstance(data, dict) else {}
            raise WhatsAppError(str(err.get("message", f"HTTP {res.status_code}")), err.get("code"))
        return str(data["messages"][0]["id"])

    async def send(self, message: OutboundMessage) -> str:
        """Tenta a mensagem livre; se a janela de 24 h estiver fechada, usa o template."""
        try:
            return await self._post(build_payload(message))
        except WhatsAppError as exc:
            if exc.code == REENGAGEMENT_ERROR and self._s.template_status:
                template = message.template or self._s.template_status
                return await self._post(
                    build_template_payload(message, template, self._s.template_lang)
                )
            raise


# --- Webhook -----------------------------------------------------------------------------------
def verify_signature(raw_body: bytes, header: str | None, app_secret: str) -> bool:
    """X-Hub-Signature-256: sha256=<hex> sobre o corpo CRU (não re-serializar o JSON)."""
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


@dataclass(frozen=True)
class InboundMessage:
    message_id: str
    sender: str  # número E.164 sem '+'
    kind: str  # text | button | audio | image | outro
    text: str = ""
    button_id: str | None = None
    context_id: str | None = None  # mensagem nossa que foi respondida (botões)
    media_id: str | None = None


def parse_webhook(payload: dict[str, Any]) -> list[InboundMessage]:
    out: list[InboundMessage] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            for msg in change.get("value", {}).get("messages", []) or []:
                kind = msg.get("type", "outro")
                context = (msg.get("context") or {}).get("id")
                common = {
                    "message_id": msg.get("id", ""),
                    "sender": msg.get("from", ""),
                    "context_id": context,
                }
                if kind == "text":
                    out.append(
                        InboundMessage(kind="text", text=msg["text"].get("body", ""), **common)
                    )
                elif kind == "interactive":
                    reply = msg.get("interactive", {}).get("button_reply") or {}
                    out.append(
                        InboundMessage(
                            kind="button",
                            text=reply.get("title", ""),
                            button_id=reply.get("id"),
                            **common,
                        )
                    )
                elif kind == "button":  # resposta a botão de template
                    button = msg.get("button", {})
                    out.append(
                        InboundMessage(
                            kind="button",
                            text=button.get("text", ""),
                            button_id=button.get("payload"),
                            **common,
                        )
                    )
                elif kind in ("audio", "image"):
                    media = msg.get(kind, {})
                    out.append(
                        InboundMessage(
                            kind=kind,
                            text=media.get("caption", ""),  # foto com legenda vira comando
                            media_id=media.get("id"),
                            **common,
                        )
                    )
                else:
                    out.append(InboundMessage(kind="outro", **common))
    return out
