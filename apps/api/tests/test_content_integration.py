"""CMS (CI com Postgres): marca, fotos de produto, página inicial e páginas institucionais."""

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
TABLES = "product_images, variants, products, designs, materials, printers, channel_fee_bands"


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (200, 40, 40)).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    command.upgrade(Config(str(API_DIR / "alembic.ini")), "head")
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    engine.dispose()
    settings = Settings(
        environment="ci",
        database_url=os.environ["DATABASE_URL"],
        admin_api_token=SecretStr("t"),
        files_dir=str(tmp_path),
        brand_cache_ttl_seconds=0,
    )
    with TestClient(create_app(settings)) as c:
        brand = c.get("/v1/admin/brand", headers=H).json()
        yield c
        c.put("/v1/admin/brand", json={k: brand[k] for k in _BRAND_FIELDS}, headers=H)


_BRAND_FIELDS = (
    "name",
    "tagline",
    "colors",
    "contact_email",
    "contact_whatsapp",
    "social",
    "cnpj",
    "legal_name",
    "voice",
)


def _sellable(c: TestClient) -> dict[str, Any]:
    mid = c.post(
        "/v1/admin/materials",
        json={"kind": "PLA", "color_name": "Azul", "color_hex": "#2244AA", "price_per_kg": "100"},
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
            "title": "Chaveiro com nome",
            "tags": ["nome"],
            "design": {"name": "Chaveiro", "origin": "parametrico"},
        },
        headers=H,
    ).json()
    c.post(
        f"/v1/admin/products/{p['id']}/variants",
        json={"grams_by_material": {str(mid): 12}, "print_seconds": 1800},
        headers=H,
    )
    c.patch(f"/v1/admin/products/{p['id']}", json={"status": "ativo"}, headers=H)
    return dict(p)


def test_marca_editavel(client: TestClient) -> None:
    brand = client.get("/v1/admin/brand", headers=H).json()
    payload = {k: brand[k] for k in _BRAND_FIELDS}
    payload.update(name="Loja Nova", colors={"light": {"primary": "#AA0000"}, "dark": {}})
    res = client.put("/v1/admin/brand", json=payload, headers=H)
    assert res.status_code == 200, res.text
    assert res.json()["colors"]["light"]["primary"] == "#AA0000"
    assert res.json()["colors"]["light"]["bg"] == brand["colors"]["light"]["bg"]  # mantém o resto
    assert client.get("/v1/brand").json()["name"] == "Loja Nova"

    bad = {**payload, "colors": {"light": {"primary": "red; } body {display:none"}, "dark": {}}}
    assert client.put("/v1/admin/brand", json=bad, headers=H).status_code == 422

    logo = client.post("/v1/admin/brand/logo/light", files={"file": ("l.png", _png())}, headers=H)
    url = logo.json()["logo_light_url"]
    assert url.startswith("/m/media/marca/")
    # /m/<chave> na vitrine → /v1/store/media/<chave> na API
    assert client.get("/v1/store/media/" + url.removeprefix("/m/")).status_code == 200


def test_fotos_de_produto_na_loja(client: TestClient) -> None:
    p = _sellable(client)
    first = client.post(
        f"/v1/admin/products/{p['id']}/images", files={"file": ("a.png", _png())}, headers=H
    )
    assert first.status_code == 201, first.text
    second = client.post(
        f"/v1/admin/products/{p['id']}/images", files={"file": ("b.png", _png())}, headers=H
    ).json()
    bad = client.post(
        f"/v1/admin/products/{p['id']}/images", files={"file": ("x.png", b"nada")}, headers=H
    )
    assert bad.status_code == 422

    card = client.get("/v1/store/products").json()[0]
    assert card["image"] == f"/m/{first.json()['thumb_key']}"
    client.post(f"/v1/admin/products/{p['id']}/images/{second['id']}/cover", headers=H)
    detail = client.get(f"/v1/store/products/{p['slug']}").json()
    assert detail["images"][0]["thumb"] == f"/m/{second['thumb_key']}"
    assert len(detail["images"]) == 2

    served = client.get(f"/v1/store/media/{second['key']}")
    assert served.headers["content-type"] == "image/webp"
    assert client.get("/v1/store/media/library/x.stl").status_code == 404

    client.delete(f"/v1/admin/products/{p['id']}/images/{second['id']}", headers=H)
    assert len(client.get(f"/v1/store/products/{p['slug']}").json()["images"]) == 1


def test_pagina_inicial_e_paginas(client: TestClient) -> None:
    p = _sellable(client)
    layout = {
        "announcement": "Frete grátis em Sorocaba!",
        "hero": {"title": "Presentes com nome", "cta_label": "Ver", "cta_href": "/c/chaveiros"},
        "sections": [
            {"title": "Chaveiros", "kind": "niche", "value": "chaveiros", "limit": 4},
            {"title": "Escolhidos", "kind": "manual", "value": f"{p['slug']}, nao-existe"},
            {"title": "Vazia", "kind": "tag", "value": "inexistente"},
        ],
    }
    assert client.put("/v1/admin/store-layout", json=layout, headers=H).status_code == 200
    home = client.get("/v1/store/home").json()
    assert home["announcement"] == "Frete grátis em Sorocaba!"
    assert [s["title"] for s in home["sections"]] == ["Chaveiros", "Escolhidos"]  # vazia some
    assert home["sections"][0]["href"] == "/c/chaveiros"

    evil = {**layout, "hero": {"cta_href": "javascript:alert(1)"}}
    assert client.put("/v1/admin/store-layout", json=evil, headers=H).status_code == 422

    pages = client.get("/v1/admin/pages", headers=H).json()
    assert {"como-comprar", "trocas-e-devolucoes", "privacidade", "sobre"} <= {
        x["slug"] for x in pages
    }
    assert client.get("/v1/store/pages/sobre").status_code == 404  # rascunho não aparece
    client.put(
        "/v1/admin/pages/sobre",
        json={"title": "Sobre nós", "body": "## Quem somos", "published": True},
        headers=H,
    )
    assert client.get("/v1/store/pages/sobre").json()["body"] == "## Quem somos"
    assert [x["slug"] for x in client.get("/v1/store/pages").json()] == ["sobre"]
    assert client.put("/v1/admin/pages/Ruim!", json={"title": "x"}, headers=H).status_code == 422
