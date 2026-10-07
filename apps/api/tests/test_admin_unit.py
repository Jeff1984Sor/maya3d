"""Testes sem banco: autenticação do admin, seleção de faixas e margem por categoria."""

from decimal import Decimal as D
from types import SimpleNamespace
from typing import Any

from fastapi.testclient import TestClient
from pydantic import SecretStr

from print3d_api.config import Settings
from print3d_api.main import create_app
from print3d_api.services.pricing import margin_for, select_bands


def _client(token: str | None) -> TestClient:
    settings = Settings(
        environment="ci", admin_api_token=SecretStr(token) if token is not None else None
    )
    return TestClient(create_app(settings))


def test_admin_desligado_sem_token_configurado() -> None:
    res = _client(None).get("/v1/admin/materials", headers={"x-admin-token": "x"})
    assert res.status_code == 503


def test_admin_exige_token() -> None:
    client = _client("segredo")
    assert client.get("/v1/admin/materials").status_code == 401
    assert client.get("/v1/admin/materials", headers={"x-admin-token": "errado"}).status_code == 401


def test_token_vazio_nao_libera() -> None:
    res = _client("").get("/v1/admin/materials", headers={"x-admin-token": ""})
    assert res.status_code == 503


def _band(channel: str, category: str | None, min_price: str, rate: str = "0.1") -> Any:
    return SimpleNamespace(
        channel=channel,
        category=category,
        min_price=D(min_price),
        max_price=None,
        commission_rate=D(rate),
        fixed_fee=D("0"),
    )


def test_faixas_da_categoria_tem_prioridade() -> None:
    rows = [
        _band("ml", None, "0", "0.12"),
        _band("ml", "religioso", "0", "0.11"),
        _band("shopee", None, "0", "0.14"),
    ]
    sel = select_bands(rows, "religioso")
    assert [b.commission_rate for b in sel["ml"]] == [D("0.11")]
    assert [b.commission_rate for b in sel["shopee"]] == [D("0.14")]  # sem específica → genérica


def test_faixas_ordenadas_por_preco() -> None:
    sel = select_bands([_band("ml", None, "79"), _band("ml", None, "0")], None)
    assert [b.min_price for b in sel["ml"]] == [D("0"), D("79")]


def test_margem_por_categoria() -> None:
    config: Any = SimpleNamespace(default_margin=D("0.40"), margin_by_category={"caixas": "0.55"})
    assert margin_for(config, "caixas") == D("0.55")
    assert margin_for(config, "outra") == D("0.40")
    assert margin_for(config, None) == D("0.40")
