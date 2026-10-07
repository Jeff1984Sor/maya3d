"""Jornada da loja (CI com Postgres): vitrine → carrinho → frete Sorocaba → checkout Pix →
acompanhamento → pagamento confirmado no painel → produção."""

import os
from collections.abc import Iterator
from decimal import Decimal as D
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
from print3d_api.services.cep import Address, CepError, normalize_cep

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="defina RUN_DB_TESTS=1 (CI)"),
]

H = {"x-admin-token": "t"}
API_DIR = Path(__file__).resolve().parents[1]
TABLES = (
    "carts, notifications, produced_fingerprints, print_jobs, order_events, order_items, orders, "
    "customers, variants, products, designs, materials, printers, channel_fee_bands, audit_log"
)


class FakeCep:
    async def lookup(self, cep: str) -> Address:
        digits = normalize_cep(cep)
        if digits.startswith("18"):
            return Address(digits, "Rua A", "Centro", "Sorocaba", "SP", "3552205")
        if digits.startswith("01"):
            return Address(digits, "Av. Paulista", "Bela Vista", "São Paulo", "SP", "3550308")
        raise CepError("CEP não encontrado")


@pytest.fixture
def client() -> Iterator[TestClient]:
    command.upgrade(Config(str(API_DIR / "alembic.ini")), "head")
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        conn.execute(
            text("UPDATE ops_config SET pix_key = 'pix@loja.test', pix_name = 'Loja Teste'")
        )
    engine.dispose()
    settings = Settings(
        environment="ci", database_url=os.environ["DATABASE_URL"], admin_api_token=SecretStr("t")
    )
    app = create_app(settings)
    app.state.cep_provider = FakeCep()
    with TestClient(app) as c:
        yield c


def _catalog(c: TestClient) -> dict[str, Any]:
    mid = c.post(
        "/v1/admin/materials",
        json={
            "kind": "PLA",
            "color_name": "Azul",
            "color_hex": "#2244AA",
            "price_per_kg": "100",
            "stock_grams": 1000,
        },
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
    p = c.post(
        "/v1/admin/products",
        json={
            "niche": "chaveiros",
            "category": "letra-nome",
            "title": "Chaveiro letra e nome",
            "customizable": True,
            "design": {"name": "Chaveiro", "origin": "parametrico"},
        },
        headers=H,
    ).json()
    c.post(
        f"/v1/admin/products/{p['id']}/variants",
        json={
            "size_label": "40mm",
            "grams_by_material": {str(mid): 12},
            "print_seconds": 1800,
            "post_minutes": 2,
        },
        headers=H,
    )
    assert (
        c.patch(f"/v1/admin/products/{p['id']}", json={"status": "ativo"}, headers=H).status_code
        == 200
    )
    return {"slug": p["slug"], "material": mid}


def test_jornada_completa(client: TestClient) -> None:
    cat = _catalog(client)
    cards = client.get("/v1/store/products?niche=chaveiros").json()
    assert cards[0]["slug"] == cat["slug"]
    assert D(cards[0]["price_from"]) > 0
    assert cards[0]["colors"] == ["#2244AA"]
    assert client.get("/v1/store/products?q=chaveiro").json()[0]["slug"] == cat["slug"]

    product = client.get(f"/v1/store/products/{cat['slug']}").json()
    variant = product["variants"][0]
    assert D(variant["price_card"]) > D(variant["price_pix"])
    assert variant["colors"][0]["material_id"] == cat["material"]
    assert "cost" not in str(product).lower()

    token = client.post("/v1/store/cart").json()["token"]
    bad = client.put(
        f"/v1/store/cart/{token}",
        json={
            "items": [
                {"variant_id": variant["id"], "quantity": 1, "personalization": {"nome": "porra"}}
            ]
        },
    )
    assert bad.status_code == 422
    cart = client.put(
        f"/v1/store/cart/{token}",
        json={
            "items": [
                {
                    "variant_id": variant["id"],
                    "quantity": 2,
                    "material_id": cat["material"],
                    "personalization": {"nome": "Ana"},
                }
            ]
        },
    ).json()
    assert cart["purchasable"] is True
    subtotal = D(cart["subtotal"])

    low = client.post("/v1/store/shipping", json={"cep": "18000-000", "subtotal": "50"}).json()
    assert low["local"] is True
    assert D(low["missing_for_free"]) == D("50")
    assert D(low["options"][0]["price"]) > 0
    high = client.post("/v1/store/shipping", json={"cep": "18000000", "subtotal": "150"}).json()
    assert D(high["options"][0]["price"]) == 0
    far = client.post("/v1/store/shipping", json={"cep": "01310-100", "subtotal": "150"}).json()
    assert far["local"] is False
    assert [o["id"] for o in far["options"]] == ["envio"]

    out = client.post(
        "/v1/store/checkout",
        json={
            "cart_token": token,
            "name": "Ana Souza",
            "email": "ana@example.com",
            "whatsapp": "+5515999990000",
            "whatsapp_opt_in": True,
            "accept_terms": True,
            "cep": "18000-000",
            "street": "Rua A",
            "number": "10",
            "shipping_option": "local",
        },
    )
    assert out.status_code == 201, out.text
    body = out.json()
    assert body["pix"]["key"] == "pix@loja.test"
    assert D(body["total"]) >= subtotal
    assert client.get(f"/v1/store/cart/{token}").json()["items"] == []

    tracking = client.get(f"/v1/store/orders/{body['public_token']}").json()
    assert tracking["status"] == "aguardando_pagamento"
    assert tracking["pix"]["amount"] == body["total"]

    admin_orders = client.get("/v1/admin/orders", headers=H).json()
    order_id = admin_orders[0]["id"]
    assert (
        client.get(f"/v1/admin/orders/{order_id}", headers=H).json()["jobs"] == []
    )  # sem pagar, sem produção
    paid = client.post(f"/v1/admin/orders/{order_id}/advance", json={"to": "pago"}, headers=H)
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "na_fila"
    assert paid.json()["jobs"][0]["quantity"] == 2
    tracking = client.get(f"/v1/store/orders/{body['public_token']}").json()
    assert [t["status"] for t in tracking["timeline"]] == [
        "aguardando_pagamento",
        "pago",
        "na_fila",
    ]
    assert tracking["pix"] is None


def test_produto_bloqueado_ou_rascunho_nao_aparece(client: TestClient) -> None:
    _catalog(client)
    client.post(
        "/v1/admin/products",
        json={
            "niche": "religioso",
            "category": "x",
            "title": "Imagem Cristo Redentor",
            "design": {"name": "x", "origin": "parametrico"},
        },
        headers=H,
    )
    slugs = [p["slug"] for p in client.get("/v1/store/products").json()]
    assert "imagem-cristo-redentor" not in slugs
    assert client.get("/v1/store/products/imagem-cristo-redentor").status_code == 404


def test_checkout_exige_termos(client: TestClient) -> None:
    cat = _catalog(client)
    vid = client.get(f"/v1/store/products/{cat['slug']}").json()["variants"][0]["id"]
    token = client.post("/v1/store/cart").json()["token"]
    client.put(f"/v1/store/cart/{token}", json={"items": [{"variant_id": vid, "quantity": 1}]})
    res = client.post(
        "/v1/store/checkout",
        json={
            "cart_token": token,
            "name": "Ana",
            "email": "ana@example.com",
            "whatsapp": "+5515999990000",
            "accept_terms": False,
            "cep": "18000000",
            "street": "Rua A",
            "number": "1",
            "shipping_option": "local",
        },
    )
    assert res.status_code == 422


class FakeQuoter:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def quote(self, origin_cep: str, dest_cep: str, parcels: list[Any]) -> list[Any]:
        from print3d_channels.shipping import ShippingRate

        self.calls.append({"origin": origin_cep, "dest": dest_cep, "parcels": parcels})
        return [
            ShippingRate("1", "Correios", "PAC", D("23.50"), 8),
            ShippingRate("2", "Correios", "SEDEX", D("39.90"), 3),
        ]


def test_frete_automatico_fora_de_sorocaba(client: TestClient) -> None:
    cat = _catalog(client)
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(text("UPDATE ops_config SET origin_cep = '18000000'"))
    engine.dispose()
    quoter = FakeQuoter()
    client.app.state.shipping_quoter = quoter  # type: ignore[attr-defined]
    vid = client.get(f"/v1/store/products/{cat['slug']}").json()["variants"][0]["id"]
    token = client.post("/v1/store/cart").json()["token"]
    client.put(f"/v1/store/cart/{token}", json={"items": [{"variant_id": vid, "quantity": 3}]})

    quote = client.post(
        "/v1/store/shipping", json={"cep": "01310-100", "subtotal": "90", "cart_token": token}
    ).json()
    assert [o["id"] for o in quote["options"]] == ["me-1", "me-2"]
    assert quote["options"][0]["label"] == "Correios PAC"
    parcel = quoter.calls[0]["parcels"][0]
    assert parcel.quantity == 3
    assert (parcel.width_cm, parcel.length_cm) == (16, 16)  # caixa padrão sem embalagem

    base = {
        "cart_token": token,
        "name": "Bia",
        "email": "bia@example.com",
        "whatsapp": "+5511999990000",
        "accept_terms": True,
        "cep": "01310-100",
        "street": "Av. Paulista",
        "number": "1000",
    }
    forged = client.post("/v1/store/checkout", json={**base, "shipping_option": "me-999"})
    assert forged.status_code == 422  # serviço que não veio na cotação

    out = client.post("/v1/store/checkout", json={**base, "shipping_option": "me-2"})
    assert out.status_code == 201, out.text
    order = client.get("/v1/admin/orders", headers=H).json()[0]
    detail = client.get(f"/v1/admin/orders/{order['id']}", headers=H).json()
    assert D(detail["shipping"]) == D("39.90")  # preço da recotação no servidor
    assert detail["shipping_address"]["option_label"] == "Correios SEDEX"
