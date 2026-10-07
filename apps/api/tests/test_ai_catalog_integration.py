"""IA no catálogo (CI com Postgres + pgvector), com fornecedores falsos:
redator por canal (conferências e aprovação), busca semântica e assistente da loja."""

import math
import os
import unicodedata
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import BaseModel, SecretStr
from sqlalchemy import create_engine, text

from print3d_ai.prompts.channel_copy import ChannelCopy, CopySet
from print3d_ai.prompts.shop_assistant import AssistantReply
from print3d_api.config import Settings
from print3d_api.main import create_app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="defina RUN_DB_TESTS=1 (CI)"),
]

H = {"x-admin-token": "t"}
API_DIR = Path(__file__).resolve().parents[1]
TABLES = (
    "channel_copies, product_embeddings, variants, products, designs, materials, printers, "
    "channel_fee_bands, audit_log"
)
VOCAB = ["madrinha", "batismo", "terco", "chaveiro", "mochila", "nome"]


def _fold(t: str) -> str:
    return unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()


class FakeEmbedder:
    """Vetor = presença de palavras-conceito: suficiente para testar a ordenação."""

    async def embed(self, texts: Sequence[str], *, model: str) -> list[list[float]]:
        out = []
        for t in texts:
            v = [1.0 if w in _fold(t) else 0.0 for w in VOCAB] + [0.01]
            n = math.sqrt(sum(x * x for x in v))
            out.append([x / n for x in v])
        return out


class FakeChat:
    def __init__(self) -> None:
        self.copy: list[ChannelCopy] = []
        self.reply: AssistantReply | None = None
        self.calls: list[dict[str, Any]] = []

    async def list_models(self) -> list[str]:
        return ["m"]

    async def complete_json(self, **kwargs: Any) -> BaseModel:
        self.calls.append(kwargs)
        if kwargs["schema"] is CopySet:
            return CopySet(items=self.copy)
        assert self.reply is not None
        return self.reply


@pytest.fixture
def chat() -> FakeChat:
    return FakeChat()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, chat: FakeChat) -> Iterator[TestClient]:
    monkeypatch.setenv("AI_API_KEY", "sk-teste")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    command.upgrade(Config(str(API_DIR / "alembic.ini")), "head")
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    engine.dispose()
    settings = Settings(
        environment="ci",
        database_url=os.environ["DATABASE_URL"],
        admin_api_token=SecretStr("t"),
        assistant_per_minute=2,
    )
    app = create_app(settings)
    app.state.ai_factory = lambda s: chat
    app.state.embedder_factory = lambda s: FakeEmbedder()
    with TestClient(app) as c:
        c.put(
            "/v1/admin/ai/config",
            json={"model_default": "m", "model_personalizer": "m", "model_embedding": "e"},
            headers=H,
        )
        yield c


def _product(c: TestClient, niche: str, title: str, tags: list[str], mid: int) -> dict[str, Any]:
    p = c.post(
        "/v1/admin/products",
        json={
            "niche": niche,
            "category": "lembranca",
            "title": title,
            "tags": tags,
            "customizable": True,
            "design": {"name": title, "origin": "parametrico"},
        },
        headers=H,
    ).json()
    c.post(
        f"/v1/admin/products/{p['id']}/variants",
        json={
            "size_label": "15 cm",
            "dims_mm": [150, 40, 5],
            "grams_by_material": {str(mid): 12},
            "print_seconds": 1800,
        },
        headers=H,
    )
    res = c.patch(f"/v1/admin/products/{p['id']}", json={"status": "ativo"}, headers=H)
    assert res.status_code == 200, res.text
    return dict(res.json())


def _catalog(c: TestClient) -> tuple[dict[str, Any], dict[str, Any]]:
    mid = c.post(
        "/v1/admin/materials",
        json={"kind": "PLA", "color_name": "Branco", "color_hex": "#FFFFFF", "price_per_kg": "100"},
        headers=H,
    ).json()["id"]
    c.post(
        "/v1/admin/printers",
        json={
            "name": "P",
            "model": "M",
            "bed_x_mm": 256,
            "bed_y_mm": 256,
            "bed_z_mm": 256,
            "avg_watts": 120,
            "hourly_wear": "0.50",
            "supported_materials": ["PLA"],
        },
        headers=H,
    )
    for band in (
        {"channel": "site_pix", "commission_rate": "0"},
        {"channel": "site_card", "commission_rate": "0.05"},
    ):
        c.post("/v1/admin/channel-fees", json=band, headers=H)
    terco = _product(c, "religioso", "Terço de batismo", ["madrinha", "batismo"], mid)
    chaveiro = _product(c, "chaveiros", "Chaveiro com nome", ["mochila", "nome"], mid)
    return terco, chaveiro


def test_redator_confere_e_aplica(client: TestClient, chat: FakeChat) -> None:
    terco, _ = _catalog(client)
    chat.copy = [
        ChannelCopy(
            channel="site",
            title="Terço de batismo personalizado para a madrinha",
            description="Lembrança delicada de 15 cm, feita em impressão 3D.",
            bullets=["Personalize com o nome"],
            keywords=["terço", "batismo"],
            hashtags=[],
        ),
        ChannelCopy(
            channel="mercadolivre",
            title="Terço Batismo Personalizado Madrinha Padrinho Lembrança Presente Decoração",
            description="Fica pronto em 7 dias. Chame no WhatsApp para personalizar.",
            bullets=[],
            keywords=["terço"],
            hashtags=["naodeveficar"],
        ),
    ]
    res = client.post(
        "/v1/admin/ai/channel-copy",
        json={"product_id": terco["id"], "channels": ["site", "mercadolivre"]},
        headers=H,
    )
    assert res.status_code == 200, res.text
    site, ml = res.json()
    assert site["channel"] == "site"
    assert site["issues"] == []  # "15 cm" está nos fatos; "3D" é permitido
    assert len(ml["title"]) <= 60
    assert ml["hashtags"] == []
    assert any("7" in i for i in ml["issues"])  # prazo inventado
    assert any("whatsapp" in i for i in ml["issues"])  # contato fora do marketplace

    fixed = client.patch(
        f"/v1/admin/ai/channel-copy/{ml['id']}",
        json={"description": "Terço personalizado com o nome, feito em impressão 3D."},
        headers=H,
    ).json()
    assert fixed["issues"] == []

    blocked = client.patch(
        f"/v1/admin/ai/channel-copy/{ml['id']}", json={"title": "Terço do Mickey"}, headers=H
    ).json()
    assert blocked["guardian_status"] == "bloqueado"
    res = client.post(
        f"/v1/admin/ai/channel-copy/{ml['id']}/status", json={"status": "aprovado"}, headers=H
    )
    assert res.status_code == 422

    assert (
        client.post(f"/v1/admin/ai/channel-copy/{site['id']}/apply", headers=H).status_code == 422
    )  # sem aprovar
    client.post(
        f"/v1/admin/ai/channel-copy/{site['id']}/status", json={"status": "aprovado"}, headers=H
    )
    applied = client.post(f"/v1/admin/ai/channel-copy/{site['id']}/apply", headers=H).json()
    assert applied["title"] == site["title"]
    listed = client.get(f"/v1/admin/ai/channel-copy?product_id={terco['id']}", headers=H).json()
    assert [r["channel"] for r in listed] == ["site", "mercadolivre"]


def test_busca_por_significado(client: TestClient) -> None:
    terco, chaveiro = _catalog(client)
    status = client.post("/v1/admin/ai/search/reindex", headers=H).json()
    assert status["done"] == 2
    assert status["indexed"] == status["products"] == 2
    assert client.post("/v1/admin/ai/search/reindex", headers=H).json()["done"] == 0

    cards = client.get("/v1/store/products", params={"q": "lembrança para madrinha"}).json()
    assert [c["slug"] for c in cards] == [terco["slug"]]
    literal = client.get("/v1/store/products", params={"q": "chaveiro"}).json()
    assert literal[0]["slug"] == chaveiro["slug"]

    test = client.get("/v1/admin/ai/search/test", params={"q": "madrinha"}, headers=H).json()
    assert test["hits"][0]["product_id"] == terco["id"]
    assert test["hits"][0]["shown"] is True


def test_assistente(client: TestClient, chat: FakeChat) -> None:
    terco, _ = _catalog(client)
    client.post("/v1/admin/ai/search/reindex", headers=H)
    assert client.get("/v1/store/settings").json()["assistant_enabled"] is True

    chat.reply = AssistantReply(
        reply="Para a madrinha, um terço de batismo personalizado é uma ótima lembrança!",
        product_slugs=[terco["slug"], "produto-inventado"],
        suggestions=["Tem com o nome do bebê?"],
    )
    body = {
        "messages": [{"role": "user", "content": "presente para madrinha"}],
        "client_id": "visitante-1",
    }
    res = client.post("/v1/store/assistant", json=body)
    assert res.status_code == 200, res.text
    out = res.json()
    assert [p["slug"] for p in out["products"]] == [terco["slug"]]  # nada inventado
    assert out["products"][0]["price_from"] is not None  # preço do banco
    assert "terco" in chat.calls[-1]["prompt"] or terco["slug"] in chat.calls[-1]["prompt"]

    chat.reply = AssistantReply(reply="Temos um do Mickey!", product_slugs=[], suggestions=[])
    assert "Mickey" not in client.post("/v1/store/assistant", json=body).json()["reply"]
    assert client.post("/v1/store/assistant", json=body).status_code == 429  # 2/min no teste
