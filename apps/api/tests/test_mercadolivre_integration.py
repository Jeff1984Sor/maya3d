"""Mercado Livre (CI com Postgres + Redis), com o ML simulado: conexão por OAuth, anúncio com
tarifa real, pedido pago importado sem contato fora da plataforma e pergunta respondida."""

import io
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr
from sqlalchemy import create_engine, text

from print3d_api.config import Settings, get_settings
from print3d_api.main import create_app
from print3d_api.services import mercadolivre as ml_service
from print3d_channels.mercadolivre import Category, ListingFee, MercadoLivreError, Tokens
from print3d_core.security import TokenVault

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="defina RUN_DB_TESTS=1 (CI)"),
]

H = {"x-admin-token": "t"}
API_DIR = Path(__file__).resolve().parents[1]
TABLES = (
    "marketplace_questions, channel_listings, channel_accounts, integration_settings, "
    "notifications, order_events, order_items, print_jobs, orders, product_images, variants, "
    "products, designs, materials"
)


class FakeML:
    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []
        self.answers: list[tuple[int, str]] = []
        self.fail_item = False
        self.resources: dict[str, dict[str, Any]] = {}

    async def exchange_code(self, code: str, redirect_uri: str, verifier: str) -> Tokens:
        assert redirect_uri == "https://api.loja.test/v1/channels/mercadolivre/callback"
        assert verifier
        return Tokens("ACC", "REF", datetime.now(UTC) + timedelta(hours=6), "777")

    async def refresh(self, refresh_token: str) -> Tokens:
        return Tokens("ACC2", "REF2", datetime.now(UTC) + timedelta(hours=6), "777")

    async def me(self, token: str) -> dict[str, Any]:
        return {"id": 777, "nickname": "LOJA3D"}

    async def predict_category(self, token: str, title: str) -> Category:
        return Category("MLB1", "Chaveiros", None)

    async def listing_fee(self, token: str, **kwargs: Any) -> ListingFee:
        return ListingFee("gold_special", Decimal("4.20"), Decimal("12"), Decimal("0"))

    async def required_attributes(self, token: str, category_id: str) -> list[dict[str, Any]]:
        return [{"id": "BRAND", "name": "Marca"}]

    async def create_item(self, token: str, item: dict[str, Any]) -> dict[str, Any]:
        if self.fail_item:
            raise MercadoLivreError("Validation error", 400, ["COLOR obrigatório"])
        self.items.append(item)
        return {"id": "MLB999", "permalink": "https://produto.mercadolivre.com.br/MLB999"}

    async def set_description(self, token: str, item_id: str, text: str) -> None:
        return None

    async def get(self, token: str, resource: str) -> dict[str, Any]:
        return self.resources[resource]

    async def answer(self, token: str, question_id: int, text: str) -> None:
        self.answers.append((question_id, text))


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeML:
    instance = FakeML()

    async def make_client(session: Any) -> FakeML:
        return instance

    monkeypatch.setattr(ml_service, "client", make_client)
    return instance


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake: FakeML) -> Iterator[TestClient]:
    monkeypatch.setenv("FERNET_KEY", TokenVault.generate_key())
    get_settings.cache_clear()
    command.upgrade(Config(str(API_DIR / "alembic.ini")), "head")
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    engine.dispose()
    settings = Settings(
        environment="ci",
        database_url=os.environ["DATABASE_URL"],
        admin_api_token=SecretStr("t"),
        files_dir=str(tmp_path),
    )
    with TestClient(create_app(settings)) as c:
        c.put(
            "/v1/admin/integrations",
            json={
                "values": {
                    "ML_CLIENT_ID": "123",
                    "ML_CLIENT_SECRET": "segredo",
                    "PUBLIC_API_URL": "https://api.loja.test",
                    "PUBLIC_STORE_URL": "https://loja.test",
                }
            },
            headers=H,
        )
        yield c
    get_settings.cache_clear()


def _connect(c: TestClient) -> None:
    url = c.post("/v1/admin/mercadolivre/connect", headers=H).json()["url"]
    state = parse_qs(urlparse(url).query)["state"][0]
    page = c.get("/v1/channels/mercadolivre/callback", params={"code": "C", "state": state})
    assert page.status_code == 200, page.text
    assert "LOJA3D" in page.text


def _product_with_photo(c: TestClient) -> tuple[int, int]:
    p = c.post(
        "/v1/admin/products",
        json={
            "niche": "chaveiros",
            "category": "chaveiro",
            "title": "Chaveiro com nome",
            "design": {"name": "x", "origin": "parametrico"},
        },
        headers=H,
    ).json()
    vid = c.post(f"/v1/admin/products/{p['id']}/variants", json={}, headers=H).json()["id"]
    buf = io.BytesIO()
    Image.new("RGB", (200, 200), (10, 10, 10)).save(buf, "PNG")
    c.post(
        f"/v1/admin/products/{p['id']}/images", files={"file": ("a.png", buf.getvalue())}, headers=H
    )
    return int(p["id"]), int(vid)


def test_conecta_anuncia_importa_pedido_e_responde(client: TestClient, fake: FakeML) -> None:
    status = client.get("/v1/admin/mercadolivre/status", headers=H).json()
    assert status["configured"] is True
    assert status["connected"] is False
    _connect(client)
    assert client.get("/v1/admin/mercadolivre/status", headers=H).json()["nickname"] == "LOJA3D"
    # callback reaproveitado não vale (state é de uso único)
    assert (
        client.get(
            "/v1/channels/mercadolivre/callback", params={"code": "C", "state": "x"}
        ).status_code
        == 400
    )

    pid, vid = _product_with_photo(client)
    prev = client.post(
        "/v1/admin/mercadolivre/preview", json={"variant_id": vid, "price": "39.90"}, headers=H
    ).json()
    assert prev["fee"] == "4.20"
    assert prev["net"] == "35.70"

    listing = client.post(
        "/v1/admin/mercadolivre/listings", json={"variant_id": vid, "price": "39.90"}, headers=H
    ).json()
    assert listing["status"] == "publicado"
    assert listing["external_id"] == "MLB999"
    assert fake.items[0]["pictures"][0]["source"].startswith("https://loja.test/m/media/")

    fake.fail_item = True
    failed = client.post(
        "/v1/admin/mercadolivre/listings", json={"variant_id": vid, "price": "39.90"}, headers=H
    ).json()
    assert failed["status"] == "erro"
    assert "COLOR obrigatório" in failed["last_error"]

    fake.resources["/orders/5001"] = {
        "id": 5001,
        "status": "paid",
        "order_items": [
            {
                "item": {"id": "MLB999", "title": "Chaveiro com nome"},
                "quantity": 3,
                "unit_price": 39.9,
            }
        ],
    }
    note = {"topic": "orders_v2", "resource": "/orders/5001", "user_id": 777, "application_id": 123}
    assert client.post("/v1/webhooks/mercadolivre", json=note).json() == {"status": "recebida"}
    client.post("/v1/webhooks/mercadolivre", json=note)  # reenvio: não duplica
    orders = [
        o
        for o in client.get("/v1/admin/orders", headers=H).json()
        if o["channel"] == "mercadolivre"
    ]
    assert len(orders) == 1
    detail = client.get(f"/v1/admin/orders/{orders[0]['id']}", headers=H).json()
    assert detail["customer"] is None  # sem contato fora da plataforma
    assert detail["items"][0]["variant_id"] == vid

    other = {**note, "user_id": 1, "resource": "/orders/9"}
    client.post("/v1/webhooks/mercadolivre", json=other)  # outra conta: ignorada

    fake.resources["/questions/88"] = {
        "id": 88,
        "item_id": "MLB999",
        "text": "Tem azul?",
        "status": "UNANSWERED",
    }
    client.post(
        "/v1/webhooks/mercadolivre",
        json={
            "topic": "questions",
            "resource": "/questions/88",
            "user_id": 777,
            "application_id": 123,
        },
    )
    q = client.get("/v1/admin/mercadolivre/questions", headers=H).json()[0]
    assert (q["text"], q["product_id"], q["status"]) == ("Tem azul?", pid, "pendente")
    done = client.post(
        f"/v1/admin/mercadolivre/questions/{q['id']}/answer", json={"text": "Temos sim!"}, headers=H
    ).json()
    assert done["status"] == "respondida"
    assert fake.answers == [(88, "Temos sim!")]


def test_sem_https_nao_conecta(client: TestClient) -> None:
    client.put(
        "/v1/admin/integrations",
        json={"values": {"PUBLIC_API_URL": "http://2.25.130.240:39000"}},
        headers=H,
    )
    res = client.post("/v1/admin/mercadolivre/connect", headers=H)
    assert res.status_code == 503
    assert "HTTPS" in res.json()["detail"]
