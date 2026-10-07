from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from print3d_api.schemas.brand import BrandPublic
from print3d_api.services.brand import BrandNotConfiguredError, BrandService

ROW = SimpleNamespace(
    name="Loja Teste", tagline="t", logo_light_url=None, logo_dark_url=None, favicon_url=None,
    colors={"light": {"primary": "#FF6B2C"}, "dark": {"primary": "#FF6B2C"}},
    fonts={"heading": "Space Grotesk", "body": "Inter"}, domain=None, contact_email=None,
    contact_whatsapp=None, social={}, voice="segredo interno", cnpj="00.000.000/0000-00",
)


def _session(row: Any) -> AsyncMock:
    session = AsyncMock()
    session.get.return_value = row
    return session


async def test_cache_evita_segunda_consulta() -> None:
    now = [0.0]
    service = BrandService(ttl_seconds=60, clock=lambda: now[0])
    session = _session(ROW)
    await service.get_public(session)
    now[0] = 30
    await service.get_public(session)
    assert session.get.await_count == 1
    now[0] = 61
    await service.get_public(session)
    assert session.get.await_count == 2


async def test_invalidate_forca_releitura() -> None:
    service = BrandService(ttl_seconds=60)
    session = _session(ROW)
    await service.get_public(session)
    service.invalidate()
    await service.get_public(session)
    assert session.get.await_count == 2


async def test_sem_linha_levanta() -> None:
    with pytest.raises(BrandNotConfiguredError):
        await BrandService(ttl_seconds=1).get_public(_session(None))


def test_schema_publico_nao_vaza_campos_internos() -> None:
    dumped = BrandPublic.model_validate(ROW).model_dump()
    assert "voice" not in dumped
    assert "cnpj" not in dumped


def test_rota_brand(client: TestClient) -> None:
    client.app.state.brand_service = BrandService(60)  # type: ignore[attr-defined]
    client.app.state.session_factory = lambda: _CtxSession(_session(ROW))  # type: ignore[attr-defined]
    res = client.get("/v1/brand")
    assert res.status_code == 200
    assert res.json()["name"] == "Loja Teste"
    assert "voice" not in res.json()


def test_rota_brand_sem_configuracao_devolve_503(client: TestClient) -> None:
    client.app.state.brand_service = BrandService(60)  # type: ignore[attr-defined]
    client.app.state.session_factory = lambda: _CtxSession(_session(None))  # type: ignore[attr-defined]
    assert client.get("/v1/brand").status_code == 503


class _CtxSession:
    """Imita `async with factory() as session`."""

    def __init__(self, session: AsyncMock) -> None:
        self._session = session

    async def __aenter__(self) -> AsyncMock:
        return self._session

    async def __aexit__(self, *exc: object) -> None:
        return None
