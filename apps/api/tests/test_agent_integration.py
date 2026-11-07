"""Assistente do painel (CI com Postgres + Redis), com IA e busca de imagens falsas: busca
roda na hora; gerar peça e alterar produto só rodam depois que o dono confirma."""

import io
import json
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

from print3d_ai.image_search import DownloadedImage, ImageHit
from print3d_ai.prompts.admin_agent import AgentStep, ToolCall
from print3d_api.config import Settings
from print3d_api.main import create_app

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="defina RUN_DB_TESTS=1 (CI)"),
]

H = {"x-admin-token": "t"}
API_DIR = Path(__file__).resolve().parents[1]
TABLES = "variants, products, designs, audit_log"
DOG_ID = "1e7ea71f-4ae1-406e-bfdb-006dbc6d151b"


def _step(message: str, *calls: tuple[str, dict[str, Any]]) -> AgentStep:
    return AgentStep(
        mensagem=message,
        chamadas=[ToolCall(ferramenta=t, argumentos_json=json.dumps(a)) for t, a in calls],  # type: ignore[arg-type]
    )


class FakeChat:
    def __init__(self) -> None:
        self.steps: list[AgentStep] = []
        self.prompts: list[str] = []

    async def list_models(self) -> list[str]:
        return ["m"]

    async def complete_json(self, **kwargs: Any) -> BaseModel:
        self.prompts.append(kwargs["prompt"])
        return self.steps.pop(0)


class FakeImages:
    hit = ImageHit(
        id=DOG_ID,
        title="Cachorro sentado",
        url="https://img.test/dog.png",
        thumbnail="https://img.test/dog-thumb.png",
        creator="Ana",
        license="CC BY 2.0",
        attribution="",
        source_page="https://img.test/page",
    )

    async def search(self, query: str, limit: int = 12) -> list[ImageHit]:
        return [self.hit]

    async def get(self, image_id: str) -> ImageHit:
        assert image_id == DOG_ID
        return self.hit

    async def download(self, url: str) -> DownloadedImage:
        buf = io.BytesIO()
        Image.new("RGB", (64, 64), (200, 200, 200)).save(buf, "PNG")
        return DownloadedImage(buf.getvalue(), "image/png", "png")


@pytest.fixture
def chat() -> FakeChat:
    return FakeChat()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, chat: FakeChat) -> Iterator[TestClient]:
    monkeypatch.setenv("AI_API_KEY", "sk-teste")
    monkeypatch.setenv("AI_PROVIDER", "openai")
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
    )
    app = create_app(settings)
    app.state.ai_factory = lambda s: chat
    app.state.image_search = FakeImages()
    with TestClient(app) as c:
        c.put("/v1/admin/ai/config", json={"model_default": "m"}, headers=H)
        yield c


def _say(c: TestClient, *turns: tuple[str, str]) -> dict[str, Any]:
    res = c.post(
        "/v1/admin/agent/chat",
        json={"turns": [{"role": r, "content": t} for r, t in turns]},
        headers=H,
    )
    assert res.status_code == 200, res.text
    return dict(res.json())


def test_busca_imagem_e_gera_peca_so_com_confirmacao(
    client: TestClient, chat: FakeChat, tmp_path: Path
) -> None:
    chat.steps = [
        _step("Vou buscar.", ("buscar_imagens", {"consulta": "sitting dog"})),
        _step("Achei 1 foto de cachorro."),
    ]
    found = _say(client, ("user", "busca foto de cachorro"))
    assert found["reply"] == "Achei 1 foto de cachorro."
    assert [i["id"] for i in found["images"]] == [DOG_ID]
    assert f"#1 id={DOG_ID}" in found["memo"]  # o painel devolve isto na conversa
    assert "Cachorro sentado" in chat.prompts[1]  # resultado da ferramenta foi para a IA
    assert found["proposals"] == []

    args = {"imagem_id": DOG_ID, "modo": "litofania", "tamanho_mm": 120}
    chat.steps = [_step("Confirme no botão.", ("gerar_peca_da_imagem", args))]
    asked = _say(
        client,
        ("user", "busca foto de cachorro"),
        ("assistant", found["memo"]),
        ("user", "faz uma litofania da 1"),
    )
    assert len(asked["proposals"]) == 1
    proposal = asked["proposals"][0]
    assert "litofania" in proposal["summary"]
    assert not (tmp_path / "uploads" / "fotos").exists()  # nada rodou antes de confirmar

    done = client.post(f"/v1/admin/agent/proposals/{proposal['id']}/confirm", headers=H)
    assert done.status_code == 200, done.text
    assert done.json()["job"].startswith("fila:")
    assert len(list((tmp_path / "uploads" / "fotos").iterdir())) == 1
    again = client.post(f"/v1/admin/agent/proposals/{proposal['id']}/confirm", headers=H)
    assert again.status_code == 422  # proposta é de uso único


def test_altera_produto_depois_de_confirmar(client: TestClient, chat: FakeChat) -> None:
    product = client.post(
        "/v1/admin/products",
        json={
            "niche": "chaveiros",
            "category": "chaveiro",
            "title": "Chaveiro velho",
            "design": {"name": "x", "origin": "parametrico"},
        },
        headers=H,
    ).json()
    chat.steps = [
        _step("Vou procurar.", ("buscar_produtos", {"texto": "chaveiro"})),
        _step(
            "Confirme a troca.",
            ("alterar_produto", {"produto_id": product["id"], "titulo": "Chaveiro novo"}),
        ),
    ]
    asked = _say(client, ("user", "troca o nome do chaveiro para Chaveiro novo"))
    assert f"#{product['id']}" in asked["proposals"][0]["summary"]
    assert client.get(f"/v1/admin/products/{product['id']}", headers=H).json()["title"] == (
        "Chaveiro velho"
    )
    pid = asked["proposals"][0]["id"]
    done = client.post(f"/v1/admin/agent/proposals/{pid}/confirm", headers=H).json()
    assert done["product_id"] == product["id"]
    after = client.get(f"/v1/admin/products/{product['id']}", headers=H).json()
    assert after["title"] == "Chaveiro novo"
    assert after["description"] == product["description"]  # campo não pedido não muda


def test_argumento_errado_volta_para_a_ia(client: TestClient, chat: FakeChat) -> None:
    chat.steps = [
        _step("Vou alterar.", ("alterar_produto", {"produto_id": "abc"})),
        _step("Não consegui: preciso do número do produto."),
    ]
    reply = _say(client, ("user", "muda o produto"))
    assert reply["proposals"] == []
    assert reply["reply"] == "Não consegui: preciso do número do produto."
    assert "erro nos argumentos" in chat.prompts[-1]


def test_plaquinhas_com_pe_viram_duas_propostas(client: TestClient, chat: FakeChat) -> None:
    def plaque(line1: str) -> tuple[str, dict[str, Any]]:
        params = {"line1": line1, "line2": "Mayris Pilates", "width_mm": 100, "mount": "pe"}
        return ("gerar_parametrico", {"modelo": "placa-nome", "parametros": params})

    chat.steps = [
        _step("Vou ver os modelos.", ("listar_parametricos", {})),
        _step("Confirme as duas placas abaixo.", plaque("Café"), plaque("Chá")),
    ]
    asked = _say(client, ("user", "2 plaquinhas Café e Chá com pezinho, Mayris Pilates, 10 cm"))
    assert "placa-nome" in chat.prompts[1]  # a lista de modelos chegou inteira à IA
    assert [p["tool"] for p in asked["proposals"]] == ["gerar_parametrico"] * 2
    assert "Café" in asked["proposals"][0]["summary"]
    done = client.post(
        f"/v1/admin/agent/proposals/{asked['proposals'][1]['id']}/confirm", headers=H
    ).json()
    assert done["job"].startswith("fila:")


def test_parametro_invalido_volta_para_a_ia(client: TestClient, chat: FakeChat) -> None:
    bad = {"modelo": "placa-nome", "parametros": {"line1": "Café", "width_mm": 10}}
    chat.steps = [
        _step("Confirme abaixo.", ("gerar_parametrico", bad)),
        _step("A largura mínima é 60 mm. Quer 60?"),
    ]
    reply = _say(client, ("user", "placa de 1 cm"))
    assert reply["proposals"] == []
    assert "erro nos argumentos" in chat.prompts[-1]


def test_botao_prometido_sem_ferramenta_e_corrigido(client: TestClient, chat: FakeChat) -> None:
    chat.steps = [
        _step("Vou gerar os modelos. Confirme no botão abaixo."),  # mentira: nenhuma chamada
        _step("Não tenho como fazer isso por aqui; use a tela Paramétricos."),
    ]
    reply = _say(client, ("user", "faz uma coisa diferente"))
    assert "não existe botão" in chat.prompts[-1]
    assert reply["reply"] == "Não tenho como fazer isso por aqui; use a tela Paramétricos."
    assert reply["proposals"] == []


def test_sem_modelo_o_assistente_desenha_a_peca(client: TestClient, chat: FakeChat) -> None:
    base = "cube([100, 6, 50]); translate([40, -14, 0]) cube([20, 34, 4]);"
    text = 'translate([50, 0, 30]) rotate([90, 0, 0]) linear_extrude(1) text("Café", size=10);'
    piece = {
        "nome": "Plaquinha Café em pé",
        "partes": [{"nome": "base", "scad": base}, {"nome": "texto", "scad": text}],
    }
    chat.steps = [_step("Desenhei a plaquinha; a prévia aparece abaixo.", ("criar_peca", piece))]
    reply = _say(client, ("user", "plaquinha Café em pé, de um jeito diferente"))
    assert reply["proposals"] == []  # criar não altera a loja: gera na hora
    assert [j["title"] for j in reply["jobs"]] == ["Plaquinha Café em pé"]
    assert reply["jobs"][0]["job"].startswith("fila:")
    assert base in reply["memo"]  # código volta na conversa para a IA poder ajustar


def test_codigo_que_le_arquivo_e_recusado(client: TestClient, chat: FakeChat) -> None:
    bad = {"nome": "x", "partes": [{"nome": "base", "scad": 'import("/srv/print3d/.env");'}]}
    chat.steps = [
        _step("Prévia abaixo.", ("criar_peca", bad)),
        _step("Não consegui desenhar desse jeito."),
    ]
    reply = _say(client, ("user", "faz a peça"))
    assert reply["jobs"] == []
    assert "sem ler arquivos" in chat.prompts[-1]


def test_ultima_fala_tem_que_ser_do_dono(client: TestClient) -> None:
    res = client.post(
        "/v1/admin/agent/chat", json={"turns": [{"role": "assistant", "content": "oi"}]}, headers=H
    )
    assert res.status_code == 422
