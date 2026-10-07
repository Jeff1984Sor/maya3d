"""Produtos ponta a ponta (CI, RUN_DB_TESTS=1): Guardião automático, ativação, SKU e preço."""

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

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="defina RUN_DB_TESTS=1 (CI)"),
]

H = {"x-admin-token": "t"}
API_DIR = Path(__file__).resolve().parents[1]
TABLES = "variants, products, designs, channel_fee_bands, packaging_boxes, printers, materials"


@pytest.fixture
def client() -> Iterator[TestClient]:
    command.upgrade(Config(str(API_DIR / "alembic.ini")), "head")
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES}, audit_log RESTART IDENTITY CASCADE"))
    engine.dispose()
    settings = Settings(
        environment="ci", database_url=os.environ["DATABASE_URL"], admin_api_token=SecretStr("t")
    )
    with TestClient(create_app(settings)) as c:
        yield c


def _product(c: TestClient, **over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "niche": "religioso",
        "category": "nossa-senhora",
        "title": "Nossa Senhora Aparecida 15cm",
        "design": {"name": "NS Aparecida", "origin": "parametrico"},
    }
    body.update(over)
    res = c.post("/v1/admin/products", json=body, headers=H)
    assert res.status_code == 201, res.text
    return dict(res.json())


def test_produto_aprovado_com_aviso_e_slug(client: TestClient) -> None:
    p = _product(client)
    assert p["guardian_status"] == "aprovado"
    assert p["status"] == "rascunho"
    assert p["slug"] == "nossa-senhora-aparecida-15cm"
    assert any("impressão 3D" in d for d in p["disclaimers"])
    p2 = _product(client)
    assert p2["slug"] == "nossa-senhora-aparecida-15cm-2"


def test_bloqueado_nao_ativa(client: TestClient) -> None:
    p = _product(client, title="Imagem Cristo Redentor 20cm")
    assert p["guardian_status"] == "bloqueado"
    res = client.patch(f"/v1/admin/products/{p['id']}", json={"status": "ativo"}, headers=H)
    assert res.status_code == 422
    assert "Guardião" in res.text


def test_corrigir_titulo_libera(client: TestClient) -> None:
    p = _product(client, title="Porta-vela Nossa Senhora")
    assert p["guardian_status"] == "bloqueado"
    fixed = client.patch(
        f"/v1/admin/products/{p['id']}",
        json={"title": "Luminária Nossa Senhora para vela LED", "status": "ativo"},
        headers=H,
    )
    assert fixed.status_code == 200, fixed.text
    assert fixed.json()["status"] == "ativo"


def test_material_minimo_sem_impressora_capaz(client: TestClient) -> None:
    p = _product(
        client,
        niche="automotivo",
        category="acabamento",
        title="Botão do vidro compatível com VW Gol G5 2009-2012",
        min_material="ASA",
    )
    assert p["available"] is False
    res = client.patch(f"/v1/admin/products/{p['id']}", json={"status": "ativo"}, headers=H)
    assert res.status_code == 422
    assert "aguardando equipamento" in res.text
    # impressora fechada cadastrada → liberado automaticamente
    client.post(
        "/v1/admin/printers",
        json={
            "name": "Fechada",
            "model": "X",
            "bed_x_mm": 256,
            "bed_y_mm": 256,
            "bed_z_mm": 256,
            "avg_watts": 150,
            "hourly_wear": "1",
            "enclosed": True,
            "supported_materials": ["PLA", "PETG", "ASA"],
        },
        headers=H,
    )
    assert client.get(f"/v1/admin/products/{p['id']}", headers=H).json()["available"] is True
    ok = client.patch(f"/v1/admin/products/{p['id']}", json={"status": "ativo"}, headers=H)
    assert ok.status_code == 200, ok.text


def test_variantes_sku_e_preco(client: TestClient) -> None:
    p = _product(client)
    pid = p["id"]
    v1 = client.post(f"/v1/admin/products/{pid}/variants", json={"size_label": "15cm"}, headers=H)
    assert v1.status_code == 201, v1.text
    assert v1.json()["sku"] == f"REL-{pid:05d}-01"
    assert v1.json()["slicing_source"] == "a_confirmar"
    vid = v1.json()["id"]

    pending = client.get(f"/v1/admin/products/{pid}/variants/{vid}/quote", headers=H).json()
    assert pending["ready"] is False

    mid = client.post(
        "/v1/admin/materials",
        json={"kind": "PLA", "color_name": "Azul", "color_hex": "#2244AA", "price_per_kg": "100"},
        headers=H,
    ).json()["id"]
    client.post(
        "/v1/admin/printers",
        json={
            "name": "P",
            "model": "M",
            "bed_x_mm": 256,
            "bed_y_mm": 256,
            "bed_z_mm": 256,
            "avg_watts": 120,
            "hourly_wear": "0.50",
            "status": "planejada",
        },
        headers=H,
    )
    client.post(
        "/v1/admin/channel-fees",
        json={"channel": "site_pix", "commission_rate": "0.0099"},
        headers=H,
    )
    upd = client.patch(
        f"/v1/admin/products/{pid}/variants/{vid}",
        json={"grams_by_material": {str(mid): 50}, "print_seconds": 7200, "post_minutes": 10},
        headers=H,
    )
    assert upd.json()["slicing_source"] == "manual"
    quote = client.get(f"/v1/admin/products/{pid}/variants/{vid}/quote", headers=H).json()
    assert quote["ready"] is True
    assert D(quote["quotes"][0]["price"]) > D(quote["cost_total"])

    summary = client.get("/v1/admin/products", headers=H).json()
    assert summary[0]["variant_count"] == 1


def test_auditoria_registra_verificacao_do_produto(client: TestClient) -> None:
    _product(client, title="Medalha CrossFit", niche="fitness", category="medalhas")
    audit = client.get("/v1/admin/audit?actor=guardiao", headers=H).json()
    assert audit[0]["action"] == "produto_verificado"
    assert audit[0]["decision"] == "bloqueado"
