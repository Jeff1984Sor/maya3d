"""WhatsApp ponta a ponta (provedor da Meta simulado): envio da caixa de saída, webhook assinado,
botão de aprovação da amostra, comandos do dono e mensagem de cliente repassada."""

import hashlib
import hmac
import itertools
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text

from print3d_api.config import Settings
from print3d_api.main import create_app
from print3d_api.services.whatsapp import same_number
from print3d_notify import OutboundMessage
from print3d_notify.meta import MetaWhatsAppProvider, WhatsAppSettings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="defina RUN_DB_TESTS=1 (CI)"),
]

H = {"x-admin-token": "t"}
SECRET = "segredo-do-app"
OWNER = "551599990000"  # dono sem o 9º dígito, como a Meta às vezes manda
CUSTOMER = "5515988887777"
API_DIR = Path(__file__).resolve().parents[1]
TABLES = (
    "inbound_messages, notifications, produced_fingerprints, print_jobs, order_events, "
    "order_items, orders, customers, variants, products, designs, materials, printers, audit_log"
)


@pytest.fixture
def sent(monkeypatch: pytest.MonkeyPatch) -> list[OutboundMessage]:
    out: list[OutboundMessage] = []
    ids = itertools.count(1)

    async def fake_send(self: MetaWhatsAppProvider, message: OutboundMessage) -> str:
        out.append(message)
        return f"wamid.{next(ids)}"

    monkeypatch.setattr(MetaWhatsAppProvider, "send", fake_send)
    return out


@pytest.fixture
def client(sent: list[OutboundMessage]) -> Iterator[TestClient]:
    command.upgrade(Config(str(API_DIR / "alembic.ini")), "head")
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        conn.execute(text("UPDATE ops_config SET owner_whatsapp = '+55 15 99999-0000'"))
    engine.dispose()
    settings = Settings(
        environment="ci", database_url=os.environ["DATABASE_URL"], admin_api_token=SecretStr("t")
    )
    wa = WhatsAppSettings(
        token=SecretStr("tok"),
        phone_number_id="1",
        graph_version="v99.0",
        app_secret=SecretStr(SECRET),
        verify_token=SecretStr("verifica"),
    )
    with TestClient(create_app(settings, wa)) as c:
        yield c


def _webhook(c: TestClient, *messages: dict[str, Any], secret: str = SECRET) -> Any:
    raw = json.dumps({"entry": [{"changes": [{"value": {"messages": list(messages)}}]}]}).encode()
    sig = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return c.post(
        "/v1/webhooks/whatsapp",
        content=raw,
        headers={"x-hub-signature-256": sig, "content-type": "application/json"},
    )


def _text(mid: str, sender: str, body: str) -> dict[str, Any]:
    return {"id": mid, "from": sender, "type": "text", "text": {"body": body}}


def _order_with_sample(c: TestClient) -> dict[str, Any]:
    mid = c.post(
        "/v1/admin/materials",
        json={"kind": "PLA", "color_name": "Azul", "color_hex": "#0000FF", "price_per_kg": "100"},
        headers=H,
    ).json()["id"]
    product = c.post(
        "/v1/admin/products",
        json={
            "niche": "chaveiros",
            "category": "letra-nome",
            "title": "Chaveiro nome",
            "design": {"name": "Chaveiro", "origin": "parametrico"},
        },
        headers=H,
    ).json()
    vid = c.post(f"/v1/admin/products/{product['id']}/variants", json={}, headers=H).json()["id"]
    cid = c.post(
        "/v1/admin/customers",
        json={"name": "Ana Souza", "whatsapp": "+" + CUSTOMER, "whatsapp_opt_in": True},
        headers=H,
    ).json()["id"]
    order = c.post(
        "/v1/admin/orders",
        json={
            "channel": "site",
            "customer_id": cid,
            "items": [
                {
                    "variant_id": vid,
                    "quantity": 20,
                    "unit_price": "10.00",
                    "personalization": {"nome": "Ana"},
                    "material_ids": [mid],
                }
            ],
        },
        headers=H,
    ).json()
    res = c.post(
        f"/v1/admin/orders/{order['id']}/advance",
        json={"to": "amostra_pronta", "media_url": "https://exemplo/amostra.jpg"},
        headers=H,
    )
    assert res.status_code == 200, res.text
    return dict(res.json())


def _notes(c: TestClient) -> list[dict[str, Any]]:
    return list(c.get("/v1/admin/notifications", headers=H).json())


def test_handshake(client: TestClient) -> None:
    ok = client.get(
        "/v1/webhooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": "verifica", "hub.challenge": "42"},
    )
    assert (ok.status_code, ok.text) == (200, "42")
    bad = client.get(
        "/v1/webhooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": "x", "hub.challenge": "42"},
    )
    assert bad.status_code == 403


def test_assinatura_invalida(client: TestClient) -> None:
    assert _webhook(client, _text("m0", CUSTOMER, "oi"), secret="outro").status_code == 401


def test_envio_e_aprovacao_por_botao(client: TestClient, sent: list[OutboundMessage]) -> None:
    order = _order_with_sample(client)
    status = client.get("/v1/admin/whatsapp/status", headers=H).json()
    assert status["configured"]
    assert status["webhook_ready"]
    assert status["pending"] >= 1

    assert client.post("/v1/admin/notifications/dispatch", headers=H).json()["sent"] >= 1
    sample_msg = next(m for m in sent if m.buttons)
    assert sample_msg.media_url == "https://exemplo/amostra.jpg"
    assert [b.id for b in sample_msg.buttons] == ["aprovar", "ajuste"]
    note = next(n for n in _notes(client) if n["template"] == "pedido_amostra_pronta")
    assert note["status"] == "enviado"
    wamid = f"wamid.{sent.index(sample_msg) + 1}"

    click = {
        "id": "b1",
        "from": CUSTOMER,
        "type": "interactive",
        "context": {"id": wamid},
        "interactive": {"type": "button_reply", "button_reply": {"id": "aprovar", "title": "Ok"}},
    }
    # outro número não aprova o pedido de ninguém
    assert _webhook(client, {**click, "id": "b0", "from": "5511911112222"}).status_code == 200
    detail = client.get(f"/v1/admin/orders/{order['id']}", headers=H).json()
    assert detail["status"] == "amostra_pronta"

    assert _webhook(client, click).json() == {"received": 1}
    assert _webhook(client, click).status_code == 200  # reenvio da Meta: idempotente
    detail = client.get(f"/v1/admin/orders/{order['id']}", headers=H).json()
    assert detail["status"] == "na_fila"
    assert sum(1 for e in detail["events"] if e["status"] == "na_fila") == 1


def test_comandos_do_dono(client: TestClient) -> None:
    order = _order_with_sample(client)
    _webhook(client, _text("c1", OWNER, f"{order['number']} aprovado"))
    detail = client.get(f"/v1/admin/orders/{order['id']}", headers=H).json()
    assert detail["status"] == "na_fila"

    _webhook(client, _text("c2", OWNER, "o que tenho pra imprimir hoje?"))
    _webhook(client, _text("c3", OWNER, "quanto vendi essa semana?"))
    _webhook(client, _text("c4", OWNER, "99999 enviado"))
    replies = [n["body"] for n in _notes(client) if n["template"] == "resposta_comando"]
    assert any("Fila de impressão" in r and "x19" in r for r in replies)
    assert any("Últimos 7 dias: 1 pedido(s), R$ 200,00" in r for r in replies)
    assert any("Não achei o pedido #99999" in r for r in replies)


def test_mensagem_de_cliente_vai_para_o_dono(client: TestClient) -> None:
    order = _order_with_sample(client)
    _webhook(client, _text("t1", CUSTOMER, "Pode ser azul mais escuro?"))
    fwd = next(n for n in _notes(client) if n["template"] == "mensagem_cliente")
    assert fwd["audience"] == "dono"
    assert f"#{order['number']}" in fwd["body"]
    assert "azul mais escuro" in fwd["body"]


def test_mesmo_numero() -> None:
    assert same_number("+55 (15) 99999-0000", "551599990000")
    assert same_number("15999990000", "5515999990000")
    assert not same_number("5515999990000", "5515999990001")
    assert not same_number(None, "1")
