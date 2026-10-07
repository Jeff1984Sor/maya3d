import hashlib
import hmac
import json
from typing import Any

import httpx
import pytest
from pydantic import SecretStr

from print3d_notify import Button, OutboundMessage
from print3d_notify.commands import parse
from print3d_notify.meta import (
    REENGAGEMENT_ERROR,
    MetaWhatsAppProvider,
    WhatsAppError,
    WhatsAppSettings,
    build_payload,
    parse_webhook,
    verify_signature,
)

SETTINGS = WhatsAppSettings(
    token=SecretStr("tok"),
    phone_number_id="123",
    graph_version="v99.0",
    template_status="atualizacao_pedido",
)


def _client(responses: list[httpx.Response], seen: list[dict[str, Any]]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "url": str(request.url),
                "json": json.loads(request.content),
                "auth": request.headers["authorization"],
            }
        )
        return responses.pop(0)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _ok(mid: str = "wamid.1") -> httpx.Response:
    return httpx.Response(200, json={"messages": [{"id": mid}]})


def test_payloads() -> None:
    text = build_payload(OutboundMessage(to="+55 (15) 99999-0000", body="oi"))
    assert text["to"] == "5515999990000"
    assert text["type"] == "text"
    image = build_payload(OutboundMessage(to="1", body="veja", media_url="https://x/y.jpg"))
    assert image["image"] == {"link": "https://x/y.jpg", "caption": "veja"}
    buttons = build_payload(
        OutboundMessage(
            to="1",
            body="Aprova?",
            media_url="https://x/a.jpg",
            buttons=[
                Button(id="aprovar", title="Aprovar"),
                Button(id="ajuste", title="Pedir ajuste"),
            ],
        )
    )
    assert buttons["type"] == "interactive"
    assert [b["reply"]["id"] for b in buttons["interactive"]["action"]["buttons"]] == [
        "aprovar",
        "ajuste",
    ]
    assert buttons["interactive"]["header"]["type"] == "image"


async def test_envia_texto() -> None:
    seen: list[dict[str, Any]] = []
    provider = MetaWhatsAppProvider(SETTINGS, _client([_ok()], seen))
    assert await provider.send(OutboundMessage(to="5515", body="oi")) == "wamid.1"
    assert seen[0]["url"] == "https://graph.facebook.com/v99.0/123/messages"
    assert seen[0]["auth"] == "Bearer tok"


async def test_janela_fechada_usa_template() -> None:
    seen: list[dict[str, Any]] = []
    closed = httpx.Response(
        400, json={"error": {"message": "re-engagement", "code": REENGAGEMENT_ERROR}}
    )
    provider = MetaWhatsAppProvider(SETTINGS, _client([closed, _ok("wamid.t")], seen))
    assert await provider.send(OutboundMessage(to="5515", body="Pedido #1\npago")) == "wamid.t"
    template = seen[1]["json"]["template"]
    assert template["name"] == "atualizacao_pedido"
    assert template["components"][0]["parameters"][0]["text"] == "Pedido #1 pago"


async def test_erro_sem_template_propaga() -> None:
    provider = MetaWhatsAppProvider(
        SETTINGS.model_copy(update={"template_status": None}),
        _client(
            [httpx.Response(400, json={"error": {"message": "x", "code": REENGAGEMENT_ERROR}})], []
        ),
    )
    with pytest.raises(WhatsAppError):
        await provider.send(OutboundMessage(to="1", body="oi"))


def test_nao_configurado() -> None:
    with pytest.raises(WhatsAppError):
        MetaWhatsAppProvider(WhatsAppSettings())


def test_assinatura() -> None:
    body = '{"a":"é"}'.encode()
    good = "sha256=" + hmac.new(b"segredo", body, hashlib.sha256).hexdigest()
    assert verify_signature(body, good, "segredo")
    assert not verify_signature(body, good, "outro")
    assert not verify_signature(body + b" ", good, "segredo")
    assert not verify_signature(body, None, "segredo")


def test_le_webhook() -> None:
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": "m1",
                                    "from": "5515999990000",
                                    "type": "text",
                                    "text": {"body": "cadê meu pedido?"},
                                },
                                {
                                    "id": "m2",
                                    "from": "5515999990000",
                                    "type": "interactive",
                                    "context": {"id": "wamid.9"},
                                    "interactive": {
                                        "type": "button_reply",
                                        "button_reply": {"id": "aprovar", "title": "Aprovar"},
                                    },
                                },
                                {
                                    "id": "m3",
                                    "from": "5515",
                                    "type": "audio",
                                    "audio": {"id": "media1"},
                                },
                            ]
                        }
                    }
                ]
            }
        ]
    }
    msgs = parse_webhook(payload)
    assert [m.kind for m in msgs] == ["text", "button", "audio"]
    assert msgs[1].button_id == "aprovar"
    assert msgs[1].context_id == "wamid.9"
    assert msgs[2].media_id == "media1"
    assert parse_webhook({"entry": [{"changes": [{"value": {"statuses": []}}]}]}) == []


@pytest.mark.parametrize(
    ("text", "kind", "number", "status"),
    [
        ("1234 enviado", "avancar", 1234, "enviado"),
        ("#1234 Imprimindo", "avancar", 1234, "imprimindo"),
        ("amostra pronta 1050", "avancar", 1050, "amostra_pronta"),
        ("pix 1001", "avancar", 1001, "pago"),
        ("1001 pago", "avancar", 1001, "pago"),
        ("o que tenho pra imprimir hoje?", "fila", None, None),
        ("quanto vendi essa semana?", "vendas", None, None),
        ("entregas de hoje", "entregas", None, None),
        ("ajuda", "ajuda", None, None),
        ("bom dia", "desconhecido", None, None),
        ("1234", "desconhecido", None, None),
    ],
)
def test_comandos_do_dono(text: str, kind: str, number: int | None, status: str | None) -> None:
    cmd = parse(text)
    assert (cmd.kind, cmd.order_number, cmd.status) == (kind, number, status)
