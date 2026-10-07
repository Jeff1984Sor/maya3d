"""Fluxo real contra Postgres (CI, RUN_DB_TESTS=1): cadastros → análise de STL → cotação."""

import io
import os
from collections.abc import Iterator
from decimal import Decimal as D
from pathlib import Path

import pytest
import trimesh
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
TABLES = "variants, products, designs, channel_fee_bands, packaging_boxes, printers, materials"


@pytest.fixture
def client() -> Iterator[TestClient]:
    command.upgrade(Config(str(API_DIR / "alembic.ini")), "head")
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    engine.dispose()
    settings = Settings(
        environment="ci",
        database_url=os.environ["DATABASE_URL"],
        admin_api_token=SecretStr(TOKEN),
    )
    with TestClient(create_app(settings)) as c:
        yield c


def _material(c: TestClient, **over: object) -> int:
    body = {"kind": "PLA", "color_name": "Branco", "color_hex": "#FFFFFF", "price_per_kg": "100"}
    body.update(over)
    res = c.post("/v1/admin/materials", json=body, headers=H)
    assert res.status_code == 201, res.text
    return int(res.json()["id"])


def _printer(c: TestClient, **over: object) -> int:
    body = {
        "name": "Teste",
        "model": "Genérica",
        "bed_x_mm": 256,
        "bed_y_mm": 256,
        "bed_z_mm": 256,
        "avg_watts": 120,
        "hourly_wear": "0.50",
        "supported_materials": ["PLA", "PETG"],
    }
    body.update(over)
    res = c.post("/v1/admin/printers", json=body, headers=H)
    assert res.status_code == 201, res.text
    return int(res.json()["id"])


def test_crud_material(client: TestClient) -> None:
    mid = _material(client, stock_grams=100)
    got = client.get(f"/v1/admin/materials/{mid}", headers=H).json()
    assert got["low_stock"] is True
    res = client.patch(f"/v1/admin/materials/{mid}", json={"stock_grams": 5000}, headers=H)
    assert res.json()["low_stock"] is False
    assert res.json()["color_name"] == "Branco"  # patch parcial preserva o resto
    assert client.delete(f"/v1/admin/materials/{mid}", headers=H).status_code == 204
    assert client.get(f"/v1/admin/materials/{mid}", headers=H).status_code == 404


def test_validacao_de_cadastro(client: TestClient) -> None:
    bad = {"kind": "PLA", "color_name": "X", "color_hex": "azul", "price_per_kg": "100"}
    assert client.post("/v1/admin/materials", json=bad, headers=H).status_code == 422


def test_cost_config_semente_e_edicao(client: TestClient) -> None:
    cfg = client.get("/v1/admin/cost-config", headers=H).json()
    assert D(cfg["min_profit"]) > 0
    cfg["min_profit"] = "9.00"
    cfg["margin_by_category"] = {"caixas": "0.5"}
    res = client.put("/v1/admin/cost-config", json=cfg, headers=H)
    assert res.status_code == 200, res.text
    assert D(res.json()["margin_by_category"]["caixas"]) == D("0.5")


def test_cotacao_completa(client: TestClient) -> None:
    mid = _material(client)
    pid = _printer(client)
    client.put(
        "/v1/admin/cost-config",
        json={
            "energy_price_kwh": "1.00",
            "labor_per_hour": "30",
            "failure_rate": "0.10",
            "min_profit": "8",
            "default_margin": "0.40",
            "margin_by_category": {},
        },
        headers=H,
    )
    for band in (
        {
            "channel": "ml_teste",
            "min_price": "0",
            "max_price": "79",
            "commission_rate": "0.12",
            "fixed_fee": "6.75",
        },
        {"channel": "ml_teste", "min_price": "79", "commission_rate": "0.12"},
        {"channel": "site_pix", "commission_rate": "0.0099"},
    ):
        assert client.post("/v1/admin/channel-fees", json=band, headers=H).status_code == 201

    res = client.post(
        "/v1/admin/pricing/quote",
        json={
            "grams_by_material": {str(mid): "50"},
            "print_minutes": 120,
            "printer_id": pid,
            "post_minutes": 10,
            "channels": ["site_pix", "ml_teste", "shopee"],
        },
        headers=H,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert D(body["cost"]["total"]) == D("12.36")  # mesmo caso do teste do motor
    quotes = {q["channel"]: q for q in body["quotes"]}
    assert D(quotes["site_pix"]["price"]) == D("20.90")
    assert D(quotes["ml_teste"]["net_profit"]) >= D("8")
    assert "nenhuma faixa" in quotes["shopee"]["error"]  # canal sem tarifa: erro claro, sem chute


def test_cotacao_avisa_material_incompativel(client: TestClient) -> None:
    mid = _material(client, kind="ASA", color_name="Preto", color_hex="#000000")
    pid = _printer(client)
    res = client.post(
        "/v1/admin/pricing/quote",
        json={"grams_by_material": {str(mid): "10"}, "print_minutes": 30, "printer_id": pid},
        headers=H,
    )
    warnings = " | ".join(res.json()["warnings"])
    assert "não imprime ASA" in warnings
    assert "fechada" in warnings


def test_cotacao_material_inexistente(client: TestClient) -> None:
    pid = _printer(client)
    res = client.post(
        "/v1/admin/pricing/quote",
        json={"grams_by_material": {"999": "10"}, "print_minutes": 30, "printer_id": pid},
        headers=H,
    )
    assert res.status_code == 404


def test_analise_de_stl_e_encaixe(client: TestClient) -> None:
    _printer(client, name="Pequena", bed_x_mm=180, bed_y_mm=180, bed_z_mm=180)
    _printer(client, name="Grande", bed_x_mm=256, bed_y_mm=256, bed_z_mm=256)
    buf = io.BytesIO()
    trimesh.creation.box((200, 50, 50)).export(buf, file_type="stl")
    res = client.post(
        "/v1/admin/mesh/analyze",
        files={"file": ("peca.stl", buf.getvalue(), "model/stl")},
        headers=H,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["report"]["watertight"] is True
    assert {p["name"]: p["fits"] for p in body["printers"]} == {"Pequena": False, "Grande": True}


def test_analise_rejeita_formato(client: TestClient) -> None:
    res = client.post(
        "/v1/admin/mesh/analyze", files={"file": ("x.step", b"x", "application/step")}, headers=H
    )
    assert res.status_code == 415


def test_comparativo_de_materiais(client: TestClient) -> None:
    pla = _material(client, kind="PLA", color_name="Branco", price_per_kg="100")
    _material(client, kind="PETG", color_name="Preto", color_hex="#000000", price_per_kg="120")
    _material(client, kind="ASA", color_name="Cinza", color_hex="#888888", price_per_kg="150")
    pid = _printer(client)  # imprime PLA e PETG, não é fechada
    client.post(
        "/v1/admin/channel-fees",
        json={"channel": "site_pix", "commission_rate": "0.0099"},
        headers=H,
    )
    res = client.post(
        "/v1/admin/pricing/compare",
        json={"reference_material_id": pla, "grams": "50", "print_minutes": 120, "printer_id": pid},
        headers=H,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["reference"] == "PLA Branco"
    grams = {r["kind"]: D(r["grams"]) for r in body["rows"]}
    assert grams == {"PLA": D("50.0"), "PETG": D("51.2"), "ASA": D("43.1")}
    totals = [D(r["cost"]["total"]) for r in body["rows"]]
    assert totals == sorted(totals)  # do mais barato ao mais caro
    asa = next(r for r in body["rows"] if r["kind"] == "ASA")
    assert any("fechada" in w for w in asa["warnings"])
    assert all(r["best_price"] is not None for r in body["rows"])
