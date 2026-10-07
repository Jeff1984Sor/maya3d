"""Tela Integrações (CI com Postgres): chaves coladas no painel ficam cifradas, nunca voltam
para o navegador e passam a valer para IA e WhatsApp sem mexer no .env."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text

from print3d_api.config import Settings, get_settings
from print3d_api.main import create_app
from print3d_core.security import TokenVault

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="defina RUN_DB_TESTS=1 (CI)"),
]

H = {"x-admin-token": "t"}
API_DIR = Path(__file__).resolve().parents[1]
KEY = "sk-proj-teste-1234567890abcd"


def _truncate() -> None:
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE integration_settings"))
    engine.dispose()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    for var in ("AI_API_KEY", "AI_PROVIDER", "WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("FERNET_KEY", TokenVault.generate_key())
    get_settings.cache_clear()
    command.upgrade(Config(str(API_DIR / "alembic.ini")), "head")
    _truncate()
    settings = Settings(
        environment="ci", database_url=os.environ["DATABASE_URL"], admin_api_token=SecretStr("t")
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c
    _truncate()
    get_settings.cache_clear()


def _field(rows: list[dict[str, object]], key: str) -> dict[str, object]:
    return next(r for r in rows if r["key"] == key)


def test_chave_de_ia_pelo_painel(client: TestClient) -> None:
    before = client.get("/v1/admin/integrations", headers=H).json()
    assert _field(before, "AI_API_KEY")["configured"] is False

    res = client.put(
        "/v1/admin/integrations",
        json={"values": {"AI_PROVIDER": "openai", "AI_API_KEY": KEY}},
        headers=H,
    )
    assert res.status_code == 200, res.text
    assert KEY not in res.text  # segredo nunca volta
    key = _field(res.json(), "AI_API_KEY")
    assert key["configured"] is True
    assert key["source"] == "painel"
    assert key["preview"] == "••••abcd"

    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as conn:
        stored = conn.execute(
            text("SELECT value FROM integration_settings WHERE key = 'AI_API_KEY'")
        ).scalar_one()
    engine.dispose()
    assert KEY not in stored  # cifrado no banco

    status = client.get("/v1/admin/ai/status", headers=H).json()
    assert status["configured"] is True
    assert status["provider"] == "openai"

    # campo vazio mantém; clear apaga
    client.put("/v1/admin/integrations", json={"values": {"AI_API_KEY": ""}}, headers=H)
    assert client.get("/v1/admin/ai/status", headers=H).json()["configured"] is True
    client.put("/v1/admin/integrations", json={"clear": ["AI_API_KEY"]}, headers=H)
    assert client.get("/v1/admin/ai/status", headers=H).json()["configured"] is False


def test_validacoes(client: TestClient) -> None:
    bad = client.put("/v1/admin/integrations", json={"values": {"AI_PROVIDER": "x"}}, headers=H)
    assert bad.status_code == 422
    bad = client.put("/v1/admin/integrations", json={"values": {"OUTRA": "x"}}, headers=H)
    assert bad.status_code == 422
    token = client.post("/v1/admin/integrations/WHATSAPP_VERIFY_TOKEN/generate", headers=H)
    assert len(token.json()["value"]) >= 24
    assert client.post("/v1/admin/integrations/AI_API_KEY/generate", headers=H).status_code == 422


def test_whatsapp_pelo_painel(client: TestClient) -> None:
    assert client.get("/v1/admin/whatsapp/status", headers=H).json()["configured"] is False
    client.put(
        "/v1/admin/integrations",
        json={
            "values": {
                "WHATSAPP_TOKEN": "EAAG-token-de-teste",
                "WHATSAPP_PHONE_NUMBER_ID": "123",
                "WHATSAPP_GRAPH_VERSION": "v99.0",
                "WHATSAPP_VERIFY_TOKEN": "verifica",
            }
        },
        headers=H,
    )
    status = client.get("/v1/admin/whatsapp/status", headers=H).json()
    assert status["configured"] is True
    assert status["graph_version"] == "v99.0"
    ok = client.get(
        "/v1/webhooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": "verifica", "hub.challenge": "7"},
    )
    assert ok.text == "7"


def test_token_de_robo(client: TestClient) -> None:
    assert (
        client.get("/v1/admin/integrations", headers={"x-robot-token": "rb_x"}).status_code == 401
    )
    issued = client.post("/v1/admin/integrations/robot-token", headers=H).json()
    robot = {"x-robot-token": issued["token"]}
    assert issued["token"].startswith("rb_")
    assert client.get("/v1/admin/integrations", headers=robot).status_code == 200
    assert issued["token"] not in client.get("/v1/admin/integrations", headers=H).text
    assert client.get("/v1/admin/integrations/robot-token", headers=H).json()["active"] is True
    client.delete("/v1/admin/integrations/robot-token", headers=H)
    assert client.get("/v1/admin/integrations", headers=robot).status_code == 401
