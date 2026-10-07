"""Guardião ponta a ponta com Postgres (CI): nichos, ajustes, licenças e auditoria."""

import os
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text

from print3d_api.config import Settings
from print3d_api.main import create_app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="defina RUN_DB_TESTS=1 (CI)"),
]

TOKEN = "token-de-teste"
H = {"x-admin-token": TOKEN}
API_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def client() -> Iterator[TestClient]:
    command.upgrade(Config(str(API_DIR / "alembic.ini")), "head")
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE audit_log, guardian_term_overrides, licenses RESTART IDENTITY"))
    engine.dispose()
    settings = Settings(
        environment="ci", database_url=os.environ["DATABASE_URL"], admin_api_token=SecretStr(TOKEN)
    )
    with TestClient(create_app(settings)) as c:
        yield c


def _check(c: TestClient, **body: object) -> dict[str, object]:
    res = c.post("/v1/admin/guardian/check", json={"origin": "parametrico", **body}, headers=H)
    assert res.status_code == 200, res.text
    return dict(res.json())


def test_nichos_semeados(client: TestClient) -> None:
    niches = client.get("/v1/admin/niches", headers=H).json()
    assert len(niches) == 9
    assert sum(n["target_count"] for n in niches) == 720
    assert niches[0]["slug"] == "religioso"


def test_bloqueia_e_audita(client: TestClient) -> None:
    out = _check(client, niche="religioso", title="Imagem Cristo Redentor 20cm")
    assert out["verdict"] == "bloqueado"
    audit = client.get("/v1/admin/audit?decision=bloqueado", headers=H).json()
    assert audit[0]["id"] == out["audit_id"]
    assert "cristo_redentor" in audit[0]["reason"]


def test_aprova_com_avisos(client: TestClient) -> None:
    out = _check(client, niche="caixas", title="Caixa de presente com ímã")
    assert out["approved"] is True
    assert any("ímã" in d for d in out["disclaimers"])  # type: ignore[union-attr]


def test_nicho_desconhecido(client: TestClient) -> None:
    res = client.post(
        "/v1/admin/guardian/check", json={"niche": "inexistente", "title": "x"}, headers=H
    )
    assert res.status_code == 422


def test_ajuste_do_admin_bloqueia_termo_novo(client: TestClient) -> None:
    assert _check(client, niche="brindes", title="Chaveiro Zumbilândia")["approved"] is True
    res = client.post(
        "/v1/admin/guardian/terms",
        json={"term": "zumbilandia", "mode": "add", "reason": "marca registrada"},
        headers=H,
    )
    assert res.status_code == 201, res.text
    assert _check(client, niche="brindes", title="Chaveiro Zumbilândia")["approved"] is False


def test_licenca_vigente_libera_personagem(client: TestClient) -> None:
    body = {"niche": "infantil", "title": "Topo de bolo Bluey", "channel": "site"}
    assert _check(client, **body)["approved"] is False
    today = date.today()
    res = client.post(
        "/v1/admin/licenses",
        json={
            "licensor": "Licenciante Teste",
            "covered_terms": ["Bluey"],
            "channels": ["site"],
            "valid_from": str(today - timedelta(days=1)),
            "valid_until": str(today + timedelta(days=30)),
        },
        headers=H,
    )
    assert res.status_code == 201, res.text
    assert _check(client, **body)["approved"] is True
    # mesmo produto no Mercado Livre: licença não cobre o canal
    assert _check(client, **{**body, "channel": "mercadolivre"})["approved"] is False


def test_licenca_com_periodo_invalido(client: TestClient) -> None:
    res = client.post(
        "/v1/admin/licenses",
        json={
            "licensor": "X",
            "covered_terms": ["y"],
            "valid_from": "2026-12-31",
            "valid_until": "2026-01-01",
        },
        headers=H,
    )
    assert res.status_code == 422
