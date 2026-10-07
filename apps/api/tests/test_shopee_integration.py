"""Shopee (CI com Postgres + Redis), com a Shopee simulada: conexão, anúncio (foto vira JPG e
sobe para a Shopee), push com assinatura conferida e pedido pago importado uma vez só."""

import hashlib
import hmac
import io
import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
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
from print3d_api.services import shopee as sp_service
from print3d_channels.shopee import ShopTokens
from print3d_core.security import TokenVault

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="defina RUN_DB_TESTS=1 (CI)"),
]

H = {"x-admin-token": "t"}
KEY = "chave-parceiro"
API_DIR = Path(__file__).resolve().parents[1]
TABLES = (
    "channel_listings, channel_accounts, integration_settings, notifications, order_events, "
    "order_items, print_jobs, orders, product_images, variants, products, designs"
)


class FakeShopee:
    def __init__(self) -> None:
        self.uploads: list[bytes] = []
        self.items: list[dict[str, Any]] = []

    def authorization_url(self, redirect: str) -> str:
        return f"https://partner.test/auth?redirect={redirect}"

    async def exchange_code(self, code: str, shop_id: str) -> ShopTokens:
        return ShopTokens("A", "R", datetime.now(UTC) + timedelta(hours=4), shop_id)

    async def shop_info(self, token: str, shop_id: str) -> dict[str, Any]:
        return {"shop_name": "Loja 3D"}

    async def recommend_category(self, token: str, shop_id: str, name: str) -> int:
        return 100

    async def upload_image(self, image: bytes, filename: str = "foto.jpg") -> str:
        self.uploads.append(image)
        return f"img{len(self.uploads)}"

    async def logistics(self, token: str, shop_id: str) -> list[int]:
        return [90001]

    async def add_item(self, token: str, shop_id: str, item: dict[str, Any]) -> str:
        self.items.append(item)
        return "777"

    async def order_detail(self, token: str, shop_id: str, order_sn: str) -> dict[str, Any]:
        return {
            "order_sn": order_sn,
            "item_list": [
                {
                    "item_id": 777,
                    "item_name": "Chaveiro",
                    "model_quantity_purchased": 2,
                    "model_discounted_price": 29.9,
                }
            ],
        }


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeShopee:
    instance = FakeShopee()

    async def make_client(session: Any) -> FakeShopee:
        return instance

    monkeypatch.setattr(sp_service, "client", make_client)
    return instance


@pytest.fixture
def client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake: FakeShopee
) -> Iterator[TestClient]:
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
                    "SHOPEE_PARTNER_ID": "1001",
                    "SHOPEE_PARTNER_KEY": KEY,
                    "PUBLIC_API_URL": "https://api.loja.test",
                }
            },
            headers=H,
        )
        yield c
    get_settings.cache_clear()


def _push(c: TestClient, payload: dict[str, Any], key: str = KEY) -> Any:
    raw = json.dumps(payload).encode()
    url = "https://api.loja.test/v1/webhooks/shopee"
    sig = hmac.new(key.encode(), url.encode() + b"|" + raw, hashlib.sha256).hexdigest()
    return c.post(
        "/v1/webhooks/shopee",
        content=raw,
        headers={"authorization": sig, "content-type": "application/json"},
    )


def test_conecta_anuncia_e_importa_pedido(client: TestClient, fake: FakeShopee) -> None:
    url = client.post("/v1/admin/shopee/connect", headers=H).json()["url"]
    redirect = parse_qs(urlparse(url).query)["redirect"][0]
    state = parse_qs(urlparse(redirect).query)["state"][0]
    page = client.get(
        "/v1/channels/shopee/callback", params={"code": "C", "shop_id": "55", "state": state}
    )
    assert "Loja 3D" in page.text
    assert client.get("/v1/admin/shopee/status", headers=H).json()["connected"] is True

    p = client.post(
        "/v1/admin/products",
        json={
            "niche": "chaveiros",
            "category": "chaveiro",
            "title": "Chaveiro com nome",
            "design": {"name": "x", "origin": "parametrico"},
        },
        headers=H,
    ).json()
    vid = client.post(f"/v1/admin/products/{p['id']}/variants", json={}, headers=H).json()["id"]
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), (200, 0, 0)).save(buf, "PNG")
    client.post(
        f"/v1/admin/products/{p['id']}/images", files={"file": ("a.png", buf.getvalue())}, headers=H
    )

    listing = client.post(
        "/v1/admin/shopee/listings", json={"variant_id": vid, "price": "29.90"}, headers=H
    ).json()
    assert listing["status"] == "publicado", listing
    assert listing["external_id"] == "shopee-777"
    assert fake.uploads[0][:2] == b"\xff\xd8"  # JPG
    assert fake.items[0]["category_id"] == 100

    assert (
        _push(
            client, {"code": 3, "shop_id": 55, "data": {"ordersn": "X1", "status": "UNPAID"}}
        ).status_code
        == 200
    )
    assert _push(client, {"code": 3, "shop_id": 55}, key="errada").status_code == 401
    paid = {"code": 3, "shop_id": 55, "data": {"ordersn": "X1", "status": "READY_TO_SHIP"}}
    _push(client, paid)
    _push(client, paid)  # reenvio: não duplica
    orders = [
        o for o in client.get("/v1/admin/orders", headers=H).json() if o["channel"] == "shopee"
    ]
    assert len(orders) == 1
    detail = client.get(f"/v1/admin/orders/{orders[0]['id']}", headers=H).json()
    assert detail["customer"] is None
    assert detail["items"][0]["variant_id"] == vid
    assert detail["items"][0]["quantity"] == 2
