"""Foto vira objeto 3D (CI com Postgres), com a IA simulada: sem chave avisa; com chave, a
foto vai para a IA, o andamento aparece e o modelo volta no tamanho pedido em STL e 3MF."""

import io
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
import trimesh
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text

from print3d_api.config import Settings, get_settings
from print3d_api.main import create_app
from print3d_api.routes.admin.photo3d import get_image_to_3d
from print3d_core.security import TokenVault
from print3d_mesh.image3d import Image3DError, Image3DTask

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="defina RUN_DB_TESTS=1 (CI)"),
]

H = {"x-admin-token": "t"}
API_DIR = Path(__file__).resolve().parents[1]
PHOTO = {"file": ("gato.png", b"\x89PNG fake", "image/png")}


class FakeImage3D:
    def __init__(self) -> None:
        self.sent: list[tuple[bytes, str]] = []
        self.steps = ["processando", "concluido"]

    async def submit(self, image: bytes, mime: str) -> str:
        self.sent.append((image, mime))
        return "task-1"

    async def task(self, task_id: str) -> Image3DTask:
        step = self.steps.pop(0)
        if step == "concluido":
            return Image3DTask(task_id, "concluido", 100, "https://x/m.stl", credits=20)
        if step == "sem_credito":
            raise Image3DError("sem créditos na Meshy", 402)
        return Image3DTask(task_id, "processando", 55)

    async def download(self, url: str) -> bytes:
        buf = io.BytesIO()
        trimesh.creation.box((1, 2, 4)).export(buf, file_type="stl")
        return buf.getvalue()


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.delenv("MESHY_API_KEY", raising=False)
    monkeypatch.setenv("FERNET_KEY", TokenVault.generate_key())
    get_settings.cache_clear()
    command.upgrade(Config(str(API_DIR / "alembic.ini")), "head")
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE integration_settings"))
    engine.dispose()
    settings = Settings(
        environment="ci",
        database_url=os.environ["DATABASE_URL"],
        admin_api_token=SecretStr("t"),
        files_dir=str(tmp_path),
    )
    with TestClient(create_app(settings)) as c:
        yield c
    get_settings.cache_clear()


def test_sem_chave_pede_para_configurar(app_client: TestClient) -> None:
    res = app_client.post("/v1/admin/photo3d", files=PHOTO, headers=H)
    assert res.status_code == 503
    assert "Integrações" in res.json()["detail"]


def test_foto_vira_modelo_no_tamanho_pedido(app_client: TestClient, tmp_path: Path) -> None:
    fake = FakeImage3D()
    app_client.app.dependency_overrides[get_image_to_3d] = lambda: fake  # type: ignore[attr-defined]

    assert (
        app_client.post("/v1/admin/photo3d", files={"file": ("x.gif", b"x")}, headers=H).status_code
        == 415
    )
    started = app_client.post(
        "/v1/admin/photo3d", files=PHOTO, data={"size_mm": "200"}, headers=H
    ).json()
    assert started["status"] == "fila"
    assert fake.sent == [(b"\x89PNG fake", "image/png")]
    ref = started["id"]

    running = app_client.get(f"/v1/admin/photo3d/{ref}", headers=H).json()
    assert (running["status"], running["progress"]) == ("processando", 55)

    done = app_client.get(f"/v1/admin/photo3d/{ref}", headers=H).json()
    assert done["status"] == "concluido"
    result = done["result"]
    assert result["bbox_mm"] == [50.0, 100.0, 200.0]
    assert result["watertight"] is True
    assert result["credits"] == 20
    folder = tmp_path / result["prefix"]
    assert (folder / "modelo.stl").is_file()
    assert (folder / "modelo.3mf").is_file()

    # depois de pronto, não consulta mais a IA (fake.steps está vazio)
    assert app_client.get(f"/v1/admin/photo3d/{ref}", headers=H).json()["status"] == "concluido"
    assert app_client.get("/v1/admin/photo3d/" + "0" * 32, headers=H).status_code == 404


def test_sem_credito_avisa_sem_perder_a_tarefa(app_client: TestClient) -> None:
    fake = FakeImage3D()
    fake.steps = ["sem_credito", "concluido"]
    app_client.app.dependency_overrides[get_image_to_3d] = lambda: fake  # type: ignore[attr-defined]
    ref = app_client.post("/v1/admin/photo3d", files=PHOTO, headers=H).json()["id"]
    res = app_client.get(f"/v1/admin/photo3d/{ref}", headers=H)
    assert res.status_code == 402
    assert app_client.get(f"/v1/admin/photo3d/{ref}", headers=H).json()["status"] == "concluido"
