"""Pix automático (CI com Postgres), com o Mercado Pago simulado: checkout gera QR Code,
a consulta aprova e o pedido vai sozinho para produção; valor divergente não libera; aviso
com assinatura inválida é recusado."""

import hashlib
import hmac
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text

from print3d_api.config import Settings, get_settings
from print3d_api.main import create_app
from print3d_api.services import payments as payments_service
from print3d_channels.mercadopago import PaymentState, PixCharge
from print3d_core.security import TokenVault

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="defina RUN_DB_TESTS=1 (CI)"),
]

H = {"x-admin-token": "t"}
API_DIR = Path(__file__).resolve().parents[1]
TABLES = (
    "payments, integration_settings, carts, notifications, produced_fingerprints, print_jobs, "
    "order_events, order_items, orders, customers, variants, products, designs, materials, "
    "printers, channel_fee_bands, audit_log"
)


class FakeMP:
    def __init__(self) -> None:
        self.status = "pending"
        self.amount: Decimal | None = None
        self.charges: list[dict[str, Any]] = []
        self.card_calls: list[dict[str, Any]] = []
        self.card_status = ("approved", "accredited")

    async def create_pix(self, **kwargs: Any) -> PixCharge:
        self.charges.append(kwargs)
        self.amount = kwargs["amount"]
        return PixCharge(
            "555", "pending", "000201PIX", "iVBOR", None, datetime.now(UTC) + timedelta(hours=24)
        )

    async def create_card(self, **kwargs: Any) -> PaymentState:
        self.card_calls.append(kwargs)
        self.amount = kwargs["amount"]
        status, detail = self.card_status
        n = len(self.card_calls)
        return PaymentState(f"77{n}", status, kwargs["amount"], None, Decimal(0), detail)

    async def payment(self, payment_id: str) -> PaymentState:
        amount = self.amount or Decimal(0)
        return PaymentState(
            payment_id,
            self.status,
            amount,
            None,
            (amount * Decimal("0.0099")).quantize(Decimal("0.01")),
        )


@pytest.fixture
def mp(monkeypatch: pytest.MonkeyPatch) -> FakeMP:
    fake = FakeMP()

    async def gateway(session: Any) -> FakeMP:
        return fake

    monkeypatch.setattr(payments_service, "gateway", gateway)
    return fake


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, mp: FakeMP, fake_cep: Any) -> Iterator[TestClient]:
    monkeypatch.setenv("FERNET_KEY", TokenVault.generate_key())
    get_settings.cache_clear()
    command.upgrade(Config(str(API_DIR / "alembic.ini")), "head")
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    engine.dispose()
    settings = Settings(
        environment="ci", database_url=os.environ["DATABASE_URL"], admin_api_token=SecretStr("t")
    )
    app = create_app(settings)
    app.state.cep_provider = fake_cep
    with TestClient(app) as c:
        c.put("/v1/admin/integrations", json={"values": {"MP_WEBHOOK_SECRET": "seg"}}, headers=H)
        yield c
        c.put("/v1/admin/integrations", json={"clear": ["MP_WEBHOOK_SECRET"]}, headers=H)
    get_settings.cache_clear()


def _checkout(c: TestClient, catalog: Any) -> dict[str, Any]:
    cat = catalog(c)
    vid = c.get(f"/v1/store/products/{cat['slug']}").json()["variants"][0]["id"]
    token = c.post("/v1/store/cart").json()["token"]
    c.put(f"/v1/store/cart/{token}", json={"items": [{"variant_id": vid, "quantity": 2}]})
    res = c.post(
        "/v1/store/checkout",
        json={
            "cart_token": token,
            "name": "Ana Souza",
            "email": "ana@example.com",
            "whatsapp": "+5515999990000",
            "accept_terms": True,
            "cep": "18000-000",
            "street": "Rua A",
            "number": "10",
            "shipping_option": "local",
        },
    )
    assert res.status_code == 201, res.text
    return dict(res.json())


def test_pix_automatico_aprova_e_vai_para_producao(
    client: TestClient, mp: FakeMP, store_catalog: Any
) -> None:
    out = _checkout(client, store_catalog)
    assert out["pix"]["automatic"] is True
    assert out["pix"]["qr_code"] == "000201PIX"
    assert mp.charges[0]["idempotency_key"].endswith("-pix")
    tracking = client.get(f"/v1/store/orders/{out['public_token']}").json()
    assert tracking["pix"]["qr_code_base64"] == "iVBOR"

    assert client.post("/v1/admin/payments/check", headers=H).json() == {"approved": 0}
    mp.status = "approved"
    assert client.post("/v1/admin/payments/check", headers=H).json() == {"approved": 1}
    tracking = client.get(f"/v1/store/orders/{out['public_token']}").json()
    assert tracking["status"] in ("na_fila", "imprimindo_amostra")
    assert tracking["pix"] is None
    assert client.post("/v1/admin/payments/check", headers=H).json() == {"approved": 0}
    bands = client.get("/v1/admin/channel-fees", headers=H).json()
    pix = next(b for b in bands if b["channel"] == "site_pix")
    assert pix["source"] == "manual"  # a do dono (vitrine de teste) não é sobrescrita


def test_valor_divergente_nao_libera(client: TestClient, mp: FakeMP, store_catalog: Any) -> None:
    out = _checkout(client, store_catalog)
    mp.status = "approved"
    mp.amount = Decimal("1.00")
    assert client.post("/v1/admin/payments/check", headers=H).json() == {"approved": 0}
    assert (
        client.get(f"/v1/store/orders/{out['public_token']}").json()["status"]
        == "aguardando_pagamento"
    )
    notes = client.get("/v1/admin/notifications", headers=H).json()
    assert any(n["template"] == "pagamento_divergente" for n in notes)


def test_aviso_assinado(client: TestClient, mp: FakeMP, store_catalog: Any) -> None:
    _checkout(client, store_catalog)
    mp.status = "approved"
    bad = client.post(
        "/v1/webhooks/mercadopago?type=payment&data.id=555",
        json={"type": "payment", "data": {"id": "555"}},
        headers={"x-signature": "ts=1,v1=errada", "x-request-id": "r1"},
    )
    assert bad.status_code == 401
    v1 = hmac.new(b"seg", b"id:555;request-id:r1;ts:1;", hashlib.sha256).hexdigest()
    ok = client.post(
        "/v1/webhooks/mercadopago?type=payment&data.id=555",
        json={"type": "payment", "data": {"id": "555"}},
        headers={"x-signature": f"ts=1,v1={v1}", "x-request-id": "r1"},
    )
    assert ok.json() == {"status": "recebida"}
    orders = client.get("/v1/admin/orders", headers=H).json()
    assert orders[0]["status"] in ("na_fila", "imprimindo_amostra")


def _card_setup(c: TestClient, mp: FakeMP) -> None:
    c.put(
        "/v1/admin/integrations",
        json={
            "values": {
                "MP_ACCESS_TOKEN": "APP_USR-acesso",
                "MP_PUBLIC_KEY": "APP_USR-publica",
                "PUBLIC_API_URL": "https://api.loja.test",
            }
        },
        headers=H,
    )


def _card_checkout(c: TestClient, catalog: Any) -> dict[str, Any]:
    cat = catalog(c)
    vid = c.get(f"/v1/store/products/{cat['slug']}").json()["variants"][0]["id"]
    token = c.post("/v1/store/cart").json()["token"]
    cart = c.put(f"/v1/store/cart/{token}", json={"items": [{"variant_id": vid, "quantity": 2}]})
    assert Decimal(cart.json()["subtotal_card"]) > Decimal(cart.json()["subtotal"])
    res = c.post(
        "/v1/store/checkout",
        json={
            "cart_token": token,
            "name": "Ana Souza",
            "email": "ana@example.com",
            "whatsapp": "+5515999990000",
            "accept_terms": True,
            "cep": "18000-000",
            "street": "Rua A",
            "number": "10",
            "shipping_option": "local",
            "payment_method": "cartao",
        },
    )
    assert res.status_code == 201, res.text
    out = dict(res.json())
    out["cart_card"] = cart.json()["subtotal_card"]
    return out


CARD = {
    "token": "tok-cartao-123456",
    "payment_method_id": "visa",
    "issuer_id": "310",
    "installments": 2,
    "payer": {"email": "ana@example.com", "identification": {"type": "CPF", "number": "123"}},
}


def test_cartao_recusado_depois_aprovado(
    client: TestClient, mp: FakeMP, store_catalog: Any
) -> None:
    _card_setup(client, mp)
    out = _card_checkout(client, store_catalog)
    assert out["pix"] is None
    assert out["card"]["public_key"] == "APP_USR-publica"
    assert Decimal(out["total"]) >= Decimal(out["cart_card"])  # preço no cartão + frete
    assert mp.charges == []  # cartão não gera Pix
    tracking = client.get(f"/v1/store/orders/{out['public_token']}").json()
    assert tracking["card"]["amount"] == out["total"]

    mp.card_status = ("rejected", "cc_rejected_insufficient_amount")
    res = client.post(f"/v1/store/orders/{out['public_token']}/card", json=CARD).json()
    assert (res["paid"], res["status"]) == (False, "rejected")
    assert "limite" in res["message"]
    assert Decimal(str(mp.card_calls[0]["amount"])) == Decimal(out["total"])  # valor do servidor

    mp.card_status = ("approved", "accredited")
    again = {**CARD, "token": "tok-cartao-999999"}
    res = client.post(f"/v1/store/orders/{out['public_token']}/card", json=again).json()
    assert res["paid"] is True
    tracking = client.get(f"/v1/store/orders/{out['public_token']}").json()
    assert tracking["status"] in ("na_fila", "imprimindo_amostra")
    assert tracking["card"] is None
    paid_again = client.post(f"/v1/store/orders/{out['public_token']}/card", json=again)
    assert paid_again.status_code == 422  # já pago


def test_pedido_pix_nao_aceita_cartao(client: TestClient, mp: FakeMP, store_catalog: Any) -> None:
    out = _checkout(client, store_catalog)
    res = client.post(f"/v1/store/orders/{out['public_token']}/card", json=CARD)
    assert res.status_code == 422
