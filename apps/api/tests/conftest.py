from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from print3d_api.config import Settings
from print3d_api.health import CheckResult, HealthChecker
from print3d_api.main import create_app
from print3d_api.services.cep import Address, CepError, normalize_cep


class _OkChecker(HealthChecker):
    def __init__(self) -> None:  # sem engine/redis reais
        pass

    async def run(self) -> dict[str, CheckResult]:
        return {"database": CheckResult(True), "redis": CheckResult(True)}


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="ci", release="test-sha")


@pytest.fixture
def client(settings: Settings) -> TestClient:
    # Sem `with`: o lifespan (engine/redis reais) não roda; injetamos stubs em app.state.
    app = create_app(settings)
    app.state.health_checker = _OkChecker()
    app.state.session_factory = MagicMock(return_value=AsyncMock())
    return TestClient(app)


# --- Vitrine de teste reaproveitada pelos testes de integração (CI com banco) ---------------
H = {"x-admin-token": "t"}


class FakeCep:
    async def lookup(self, cep: str) -> Address:
        digits = normalize_cep(cep)
        if digits.startswith("18"):
            return Address(digits, "Rua A", "Centro", "Sorocaba", "SP", "3552205")
        if digits.startswith("01"):
            return Address(digits, "Av. Paulista", "Bela Vista", "São Paulo", "SP", "3550308")
        raise CepError("CEP não encontrado")


@pytest.fixture
def fake_cep() -> FakeCep:
    return FakeCep()


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


@pytest.fixture
def store_catalog() -> Callable[[TestClient], dict[str, Any]]:
    """Cria material, impressora, tarifas do site e um produto à venda."""
    return _catalog
