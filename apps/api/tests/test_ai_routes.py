"""Rotas de IA: sem chave = desligado com mensagem clara; com fornecedor falso = sugestão
validada, auditada e passada pelo Guardião (CI com banco para o fluxo completo)."""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import BaseModel, SecretStr

from print3d_ai.prompts.enrich_product import FaqItem, ProductSuggestion
from print3d_api.config import Settings
from print3d_api.main import create_app

H = {"x-admin-token": "t"}
API_DIR = Path(__file__).resolve().parents[1]


class FakeProvider:
    def __init__(self, title: str) -> None:
        self.title = title
        self.calls: list[dict[str, Any]] = []

    async def list_models(self) -> list[str]:
        return ["modelo-a", "modelo-b"]

    async def complete_json(self, **kwargs: Any) -> BaseModel:
        self.calls.append(kwargs)
        return ProductSuggestion(
            title=self.title,
            title_short=self.title[:60],
            category="nossa-senhora",
            subcategory="aparecida",
            description="Imagem acolhedora para o seu oratório.",
            bullets=["Feita em impressão 3D; linhas de camada podem aparecer."],
            faq=[FaqItem(question="Pode pintar?", answer="Sim, há versão pintada à mão.")],
            tags=["aparecida"],
            occasions=["12 de outubro"],
            color_ideas=["manto azul"],
            seo_title=self.title[:70],
            seo_description="Imagem de Nossa Senhora Aparecida.",
        )


pytestmark_db = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1", reason="defina RUN_DB_TESTS=1 (CI)"
)


@pytest.fixture
def db_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("AI_API_KEY", "sk-teste")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    command.upgrade(Config(str(API_DIR / "alembic.ini")), "head")
    settings = Settings(
        environment="ci", database_url=os.environ["DATABASE_URL"], admin_api_token=SecretStr("t")
    )
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


@pytestmark_db
@pytest.mark.integration
def test_sem_modelo_escolhido_avisa(db_client: TestClient) -> None:
    db_client.app.state.ai_factory = lambda s: FakeProvider("x")  # type: ignore[attr-defined]
    db_client.put("/v1/admin/ai/config", json={}, headers=H)
    res = db_client.post(
        "/v1/admin/ai/enrich-product",
        json={"hint": "Nossa Senhora Aparecida", "niche": "religioso"},
        headers=H,
    )
    assert res.status_code == 503
    assert "escolha o modelo" in res.text


@pytestmark_db
@pytest.mark.integration
def test_status_lista_modelos_e_enriquece(db_client: TestClient) -> None:
    fake = FakeProvider("Nossa Senhora Aparecida 15cm")
    db_client.app.state.ai_factory = lambda s: fake  # type: ignore[attr-defined]
    status = db_client.put(
        "/v1/admin/ai/config", json={"model_default": "modelo-a"}, headers=H
    ).json()
    assert status["configured"] is True
    assert status["available_models"] == ["modelo-a", "modelo-b"]
    assert status["models"]["default"] == "modelo-a"

    res = db_client.post(
        "/v1/admin/ai/enrich-product",
        json={"hint": "Nossa Senhora Aparecida 15cm manto azul", "niche": "religioso"},
        headers=H,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["guardian_approved"] is True
    assert body["model"] == "modelo-a"
    assert "reverente" in fake.calls[0]["system"].lower() or "acolhedora" in fake.calls[0]["system"]


@pytestmark_db
@pytest.mark.integration
def test_sugestao_bloqueada_pelo_guardiao(db_client: TestClient) -> None:
    db_client.app.state.ai_factory = lambda s: FakeProvider("Imagem Cristo Redentor")  # type: ignore[attr-defined]
    db_client.put("/v1/admin/ai/config", json={"model_default": "modelo-a"}, headers=H)
    body = db_client.post(
        "/v1/admin/ai/enrich-product",
        json={"hint": "Cristo Redentor grande", "niche": "religioso"},
        headers=H,
    ).json()
    assert body["guardian_approved"] is False
    assert body["violations"][0]["code"] == "cristo_redentor"
