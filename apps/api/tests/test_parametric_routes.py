"""Rotas de paramétricos sem banco: catálogo, validação, status de job e download seguro."""

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from pydantic import SecretStr

from print3d_api.config import Settings
from print3d_api.deps import get_queue
from print3d_api.main import create_app

H = {"x-admin-token": "t"}


def _client(tmp_path: Path, queue: Any = None) -> TestClient:
    app = create_app(
        Settings(environment="ci", admin_api_token=SecretStr("t"), files_dir=str(tmp_path))
    )
    app.state.session_factory = MagicMock(return_value=AsyncMock())
    app.dependency_overrides[get_queue] = lambda: queue or AsyncMock()
    return TestClient(app)


def test_lista_modelos_com_schema(tmp_path: Path) -> None:
    models = {m["slug"]: m for m in _client(tmp_path).get("/v1/admin/parametric", headers=H).json()}
    assert {"chaveiro-letra-nome", "caixa"} <= set(models)
    props = models["chaveiro-letra-nome"]["params_schema"]["properties"]
    assert props["letter_size_mm"]["title"] == "Tamanho da letra (mm)"


def test_modelo_inexistente(tmp_path: Path) -> None:
    res = _client(tmp_path).post("/v1/admin/parametric/nada/generate", json={}, headers=H)
    assert res.status_code == 404


def test_parametros_invalidos_nem_chegam_na_fila(tmp_path: Path) -> None:
    queue = AsyncMock()
    res = _client(tmp_path, queue).post(
        "/v1/admin/parametric/caixa/generate", json={"width_mm": 5}, headers=H
    )
    assert res.status_code == 422
    queue.enqueue_job.assert_not_awaited()


def test_download_seguro(tmp_path: Path) -> None:
    (tmp_path / "parametric" / "j1").mkdir(parents=True)
    (tmp_path / "parametric" / "j1" / "completo.stl").write_bytes(b"solid x")
    client = _client(tmp_path)
    ok = client.get("/v1/admin/files/parametric/j1/completo.stl", headers=H)
    assert ok.status_code == 200
    assert ok.content == b"solid x"
    assert client.get("/v1/admin/files/parametric/j1/nada.stl", headers=H).status_code == 404
    assert client.get("/v1/admin/files/parametric/../../etc/passwd", headers=H).status_code in (
        400,
        404,
    )


def test_download_exige_token(tmp_path: Path) -> None:
    assert _client(tmp_path).get("/v1/admin/files/x.stl").status_code == 401
