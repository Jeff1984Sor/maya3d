"""Biblioteca (CI com Postgres): coleção → envio de arquivos → resultado do worker →
modelo vira produto; sem licença o Guardião bloqueia, ao preencher a licença libera."""

import io
import json
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

from print3d_api.config import Settings
from print3d_api.main import create_app
from print3d_mesh.library import organize

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="defina RUN_DB_TESTS=1 (CI)"),
]

H = {"x-admin-token": "t"}
API_DIR = Path(__file__).resolve().parents[1]
TABLES = "library_models, library_collections, variants, products, designs, audit_log"


@pytest.fixture
def files(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def client(files: Path) -> Iterator[TestClient]:
    command.upgrade(Config(str(API_DIR / "alembic.ini")), "head")
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    engine.dispose()
    settings = Settings(
        environment="ci",
        database_url=os.environ["DATABASE_URL"],
        admin_api_token=SecretStr("t"),
        files_dir=str(files),
    )
    with TestClient(create_app(settings)) as c:
        yield c


def _stl_bytes(size: tuple[float, float, float]) -> bytes:
    buf = io.BytesIO()
    trimesh.creation.box(size).export(buf, file_type="stl")
    return buf.getvalue()


def _worker(files: Path, slug: str) -> None:
    """Faz o papel do worker (process_library) dentro do teste."""
    base = files / "library" / slug
    result = organize(base / "_envios", base / "modelos", (256, 256, 256))
    payload = {"status": "pronto", "finished_at": "2026-10-07T20:00:00+00:00", **result}
    (base / "colecao.json").write_text(json.dumps(payload))


def test_acervo_vira_produto(client: TestClient, files: Path) -> None:
    res = client.post(
        "/v1/admin/library/collections",
        json={"title": "Terços Personalizados", "niche": "religioso", "category": "tercos"},
        headers=H,
    )
    assert res.status_code == 201, res.text
    slug = res.json()["slug"]
    assert slug == "tercos-personalizados"

    bad = client.post(
        f"/v1/admin/library/collections/{slug}/files",
        files={"file": ("virus.exe", b"x")},
        headers=H,
    )
    assert bad.status_code == 422
    up = client.post(
        f"/v1/admin/library/collections/{slug}/files",
        files={"file": ("Terço Mariano 3d model.stl", _stl_bytes((60, 40, 5)))},
        headers=H,
    )
    assert up.json()["name"] == "terco-mariano-3d-model.stl"
    cols = client.get("/v1/admin/library/collections", headers=H).json()
    assert cols[0]["pending_files"] == ["terco-mariano-3d-model.stl"]

    _worker(files, slug)
    models = client.get(f"/v1/admin/library/collections/{slug}/models", headers=H).json()
    assert len(models) == 1
    model = models[0]
    assert model["title"] == "Terco mariano"
    assert model["fits"] is True

    made = client.post(f"/v1/admin/library/models/{model['id']}/product", json={}, headers=H)
    assert made.status_code == 200, made.text
    assert made.json()["guardian"] == "bloqueado"  # sem licença declarada
    again = client.post(f"/v1/admin/library/models/{model['id']}/product", json={}, headers=H)
    assert again.status_code == 422

    lic = client.put(
        f"/v1/admin/library/collections/{slug}/license",
        json={"license_text": "licença comercial — compra de 07/10/2026"},
        headers=H,
    )
    assert lic.json() == {"rechecked": 1}
    product = client.get(f"/v1/admin/products/{made.json()['product_id']}", headers=H).json()
    assert product["guardian_status"] == "aprovado"
    assert product["design"]["source_file_url"].endswith("terco-mariano-3d-model.stl")

    col = client.get("/v1/admin/library/collections", headers=H).json()[0]
    assert (col["models"], col["products"], col["status"]) == (1, 1, "pronto")


def test_capa_abre_como_imagem(client: TestClient, files: Path) -> None:
    cover = files / "library" / "x" / "modelos" / "a" / "capa.png"
    cover.parent.mkdir(parents=True)
    from PIL import Image

    Image.new("RGB", (4, 4)).save(cover)
    res = client.get("/v1/admin/files/library/x/modelos/a/capa.png", headers=H)
    assert res.headers["content-type"] == "image/png"
    assert res.headers["content-disposition"].startswith("inline")
