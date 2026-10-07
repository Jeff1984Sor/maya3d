"""Guardião visual (CI com Postgres), com IA falsa: foto com personagem bloqueia o produto;
o dono libera com motivo (auditado) e o produto volta a ser aprovado."""

import io
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import BaseModel, SecretStr
from sqlalchemy import create_engine, text

from print3d_ai.prompts.guardian_visual import Finding, VisualVerdict
from print3d_api.config import Settings
from print3d_api.main import create_app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="defina RUN_DB_TESTS=1 (CI)"),
]

H = {"x-admin-token": "t"}
API_DIR = Path(__file__).resolve().parents[1]


class FakeVision:
    def __init__(self) -> None:
        self.verdict = VisualVerdict(findings=[], summary="foto limpa")
        self.calls: list[dict[str, Any]] = []

    async def list_models(self) -> list[str]:
        return ["m"]

    async def complete_json(self, **kwargs: Any) -> BaseModel:
        self.calls.append(kwargs)
        return self.verdict


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (300, 300), (250, 250, 250)).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def vision() -> FakeVision:
    return FakeVision()


@pytest.fixture
def client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, vision: FakeVision
) -> Iterator[TestClient]:
    monkeypatch.setenv("AI_API_KEY", "sk-teste")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    command.upgrade(Config(str(API_DIR / "alembic.ini")), "head")
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE product_images, variants, products, designs RESTART IDENTITY CASCADE")
        )
    engine.dispose()
    settings = Settings(
        environment="ci",
        database_url=os.environ["DATABASE_URL"],
        admin_api_token=SecretStr("t"),
        files_dir=str(tmp_path),
    )
    app = create_app(settings)
    app.state.ai_factory = lambda s: vision
    with TestClient(app) as c:
        c.put("/v1/admin/ai/config", json={"model_guardian": "visao"}, headers=H)
        yield c
        c.put("/v1/admin/ai/config", json={}, headers=H)


def _product(c: TestClient) -> int:
    p = c.post(
        "/v1/admin/products",
        json={
            "niche": "chaveiros",
            "category": "chaveiro",
            "title": "Chaveiro de ratinho",
            "design": {"name": "x", "origin": "parametrico"},
        },
        headers=H,
    ).json()
    return int(p["id"])


def test_foto_com_personagem_bloqueia_e_dono_libera(client: TestClient, vision: FakeVision) -> None:
    pid = _product(client)
    assert (
        client.get(f"/v1/admin/products/{pid}", headers=H).json()["guardian_status"] == "aprovado"
    )

    vision.verdict = VisualVerdict(
        findings=[Finding(kind="personagem", description="Mickey Mouse", confidence=0.93)],
        summary="personagem da Disney na peça",
    )
    up = client.post(
        f"/v1/admin/products/{pid}/images", files={"file": ("a.png", _png())}, headers=H
    )
    assert up.status_code == 201, up.text
    # análise automática roda depois da resposta (BackgroundTasks)
    images = client.get(f"/v1/admin/products/{pid}/images", headers=H).json()
    assert images[0]["visual_status"] == "bloqueado"
    assert vision.calls[-1]["model"] == "visao"
    assert vision.calls[-1]["images"][0].media_type == "image/webp"
    product = client.get(f"/v1/admin/products/{pid}", headers=H).json()
    assert product["guardian_status"] == "bloqueado"
    assert "Guardião visual" in product["guardian_reason"]

    short = client.post(
        f"/v1/admin/products/{pid}/images/{images[0]['id']}/release",
        json={"reason": "x"},
        headers=H,
    )
    assert short.status_code == 422  # motivo obrigatório
    client.post(
        f"/v1/admin/products/{pid}/images/{images[0]['id']}/release",
        json={"reason": "desenho próprio, não é o personagem"},
        headers=H,
    )
    assert (
        client.get(f"/v1/admin/products/{pid}", headers=H).json()["guardian_status"] == "aprovado"
    )

    # nova verificação não passa por cima da decisão do dono
    calls = len(vision.calls)
    again = client.post(f"/v1/admin/products/{pid}/images/visual-check", headers=H).json()
    assert again[0]["visual_status"] == "liberado"
    assert len(vision.calls) == calls


def test_foto_limpa_fica_ok(client: TestClient, vision: FakeVision) -> None:
    pid = _product(client)
    client.post(f"/v1/admin/products/{pid}/images", files={"file": ("a.png", _png())}, headers=H)
    images = client.get(f"/v1/admin/products/{pid}/images", headers=H).json()
    assert images[0]["visual_status"] == "ok"
    assert (
        client.get(f"/v1/admin/products/{pid}", headers=H).json()["guardian_status"] == "aprovado"
    )
