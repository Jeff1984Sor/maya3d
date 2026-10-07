"""DoD da Fase 5 (spec): pedido de 25 un. passa pela amostra, é aprovado e libera o resto;
um segundo pedido igual pula a amostra. Mais: fila por material, notificações e regras."""

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

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="defina RUN_DB_TESTS=1 (CI)"),
]

H = {"x-admin-token": "t"}
API_DIR = Path(__file__).resolve().parents[1]
TABLES = (
    "notifications, produced_fingerprints, print_jobs, order_events, order_items, orders, "
    "customers, variants, products, designs, materials, printers, audit_log"
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    command.upgrade(Config(str(API_DIR / "alembic.ini")), "head")
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
        conn.execute(text("UPDATE ops_config SET owner_whatsapp = '+5515999990000'"))
    engine.dispose()
    settings = Settings(
        environment="ci", database_url=os.environ["DATABASE_URL"], admin_api_token=SecretStr("t")
    )
    with TestClient(create_app(settings)) as c:
        yield c


def _setup(c: TestClient) -> dict[str, int]:
    mid = c.post(
        "/v1/admin/materials",
        json={"kind": "PLA", "color_name": "Branco", "color_hex": "#FFFFFF", "price_per_kg": "100"},
        headers=H,
    ).json()["id"]
    product = c.post(
        "/v1/admin/products",
        json={
            "niche": "chaveiros",
            "category": "letra-nome",
            "title": "Chaveiro letra e nome",
            "design": {"name": "Chaveiro", "origin": "parametrico"},
        },
        headers=H,
    ).json()
    vid = c.post(f"/v1/admin/products/{product['id']}/variants", json={}, headers=H).json()["id"]
    cid = c.post(
        "/v1/admin/customers",
        json={
            "name": "Paróquia São José",
            "kind": "pj",
            "whatsapp": "+5515988887777",
            "whatsapp_opt_in": True,
        },
        headers=H,
    ).json()["id"]
    return {"material": mid, "variant": vid, "customer": cid}


def _order(c: TestClient, ids: dict[str, int], qty: int, **over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "channel": "site",
        "customer_id": ids["customer"],
        "items": [
            {
                "variant_id": ids["variant"],
                "quantity": qty,
                "unit_price": "12.90",
                "personalization": {"nome": "Ana"},
                "material_ids": [ids["material"]],
            }
        ],
    }
    body.update(over)
    res = c.post("/v1/admin/orders", json=body, headers=H)
    assert res.status_code == 201, res.text
    return dict(res.json())


def _advance(c: TestClient, order_id: int, to: str, **extra: Any) -> dict[str, Any]:
    res = c.post(f"/v1/admin/orders/{order_id}/advance", json={"to": to, **extra}, headers=H)
    assert res.status_code == 200, res.text
    return dict(res.json())


def test_amostra_aprovada_libera_resto_e_segundo_pedido_pula(client: TestClient) -> None:
    ids = _setup(client)
    o = _order(client, ids, 25)
    assert o["status"] == "imprimindo_amostra"
    assert o["items"][0]["needs_sample"] is True
    assert [(j["quantity"], j["is_sample"]) for j in o["jobs"]] == [(1, True)]
    assert o["total"] == "322.50"

    # imprime a amostra, tira foto, cliente aprova
    client.post(
        f"/v1/admin/print-jobs/{o['jobs'][0]['id']}", json={"action": "concluir"}, headers=H
    )
    _advance(client, o["id"], "amostra_pronta", media_url="https://exemplo/foto.jpg")
    done = _advance(client, o["id"], "na_fila", note="cliente aprovou")
    assert sorted((j["quantity"], j["is_sample"]) for j in done["jobs"]) == [(1, True), (24, False)]
    assert done["progress"] == "1 de 25 impressas"

    # mesmo pedido de novo: pula a amostra
    o2 = _order(client, ids, 25)
    assert o2["status"] == "na_fila"
    assert o2["items"][0]["needs_sample"] is False
    assert [j["quantity"] for j in o2["jobs"]] == [25]


def test_ajuste_conta_rodadas(client: TestClient) -> None:
    ids = _setup(client)
    o = _order(client, ids, 30)
    _advance(client, o["id"], "amostra_pronta")
    d = _advance(client, o["id"], "ajuste_solicitado", note="nome maior")
    assert d["sample_rounds"] == 1
    d = _advance(client, o["id"], "imprimindo_amostra")
    assert sum(1 for j in d["jobs"] if j["is_sample"]) == 2


def test_pedido_pequeno_vai_direto_e_fluxo_completo(client: TestClient) -> None:
    ids = _setup(client)
    o = _order(client, ids, 3)
    assert o["status"] == "na_fila"
    job_id = o["jobs"][0]["id"]
    client.post(f"/v1/admin/print-jobs/{job_id}", json={"action": "iniciar"}, headers=H)
    assert client.get(f"/v1/admin/orders/{o['id']}", headers=H).json()["status"] == "imprimindo"
    client.post(f"/v1/admin/print-jobs/{job_id}", json={"action": "concluir"}, headers=H)
    for step in ("acabamento", "embalado", "enviado", "entregue"):
        last = _advance(client, o["id"], step)
    assert last["progress"] == "3 de 3 impressas"
    assert [e["status"] for e in last["events"]][-1] == "entregue"


def test_transicao_invalida(client: TestClient) -> None:
    ids = _setup(client)
    o = _order(client, ids, 2)
    res = client.post(f"/v1/admin/orders/{o['id']}/advance", json={"to": "entregue"}, headers=H)
    assert res.status_code == 422


def test_falha_de_impressao_volta_para_fila(client: TestClient) -> None:
    ids = _setup(client)
    o = _order(client, ids, 2)
    job_id = o["jobs"][0]["id"]
    res = client.post(
        f"/v1/admin/print-jobs/{job_id}", json={"action": "falhou", "reason": "descolou"}, headers=H
    )
    assert res.json()["status"] == "falhou"
    queue = client.get("/v1/admin/print-queue", headers=H).json()
    assert queue[0]["materials"] == ["PLA Branco"]
    assert queue[0]["total_pieces"] == 2


def test_notificacoes_respeitam_canal(client: TestClient) -> None:
    ids = _setup(client)
    _order(client, ids, 2)
    _order(client, ids, 2, channel="mercadolivre", customer_id=None, external_id="ML-1")
    notes = client.get("/v1/admin/notifications", headers=H).json()
    owner = [n for n in notes if n["audience"] == "dono"]
    customer = [n for n in notes if n["audience"] == "cliente"]
    assert len(owner) == 2  # dono recebe as duas vendas
    assert all(n["status"] == "pendente" for n in owner)  # sem provedor: fica na fila
    assert len(customer) == 1  # Mercado Livre nunca gera contato fora da plataforma
    assert "Paróquia" in customer[0]["body"]


def test_cancelar_cancela_fila(client: TestClient) -> None:
    ids = _setup(client)
    o = _order(client, ids, 2)
    d = _advance(client, o["id"], "cancelado", note="cliente desistiu")
    assert all(j["status"] == "cancelado" for j in d["jobs"])
    assert client.get("/v1/admin/print-queue", headers=H).json() == []
