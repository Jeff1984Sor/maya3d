import io
import json

import httpx
import pytest
import trimesh

from print3d_mesh.image3d import Image3DError, ImageTo3D, MeshyImageTo3D, prepare_for_print


def _meshy(handler: httpx.MockTransport, model: str | None = None) -> MeshyImageTo3D:
    return MeshyImageTo3D("chave", model=model, client=httpx.AsyncClient(transport=handler))


async def test_envia_foto_como_data_uri_sem_textura() -> None:
    seen: dict[str, object] = {}

    def handle(req: httpx.Request) -> httpx.Response:
        seen["auth"] = req.headers["authorization"]
        seen["body"] = json.loads(req.content)
        return httpx.Response(202, json={"result": "t-1"})

    provider = _meshy(httpx.MockTransport(handle))
    assert isinstance(provider, ImageTo3D)
    assert await provider.submit(b"\x89PNG", "image/png") == "t-1"
    body = seen["body"]
    assert isinstance(body, dict)
    assert seen["auth"] == "Bearer chave"
    assert body["image_url"].startswith("data:image/png;base64,")
    assert body["should_texture"] is False
    assert body["target_formats"] == ["stl"]
    assert "ai_model" not in body  # modelo só quando o dono escolhe no painel


async def test_modelo_escolhido_no_painel_vai_no_pedido() -> None:
    def handle(req: httpx.Request) -> httpx.Response:
        assert json.loads(req.content)["ai_model"] == "meshy-6-lite"
        return httpx.Response(202, json={"result": "t-2"})

    assert await _meshy(httpx.MockTransport(handle), "meshy-6-lite").submit(b"x", "image/jpeg")


async def test_status_e_link_do_stl() -> None:
    answers = iter(
        [
            {"status": "IN_PROGRESS", "progress": 40},
            {
                "status": "SUCCEEDED",
                "progress": 100,
                "model_urls": {"stl": "https://assets.meshy.ai/m.stl"},
                "consumed_credits": 20,
            },
            {"status": "FAILED", "task_error": {"message": "foto sem objeto"}},
        ]
    )
    provider = _meshy(httpx.MockTransport(lambda req: httpx.Response(200, json=next(answers))))
    running = await provider.task("t")
    assert (running.status, running.progress) == ("processando", 40)
    done = await provider.task("t")
    assert (done.status, done.model_url, done.credits) == (
        "concluido",
        "https://assets.meshy.ai/m.stl",
        20,
    )
    failed = await provider.task("t")
    assert (failed.status, failed.error) == ("falhou", "foto sem objeto")


@pytest.mark.parametrize(("code", "text"), [(401, "inválida"), (402, "créditos"), (403, "Pro")])
async def test_erros_viram_mensagem_clara(code: int, text: str) -> None:
    provider = _meshy(httpx.MockTransport(lambda req: httpx.Response(code, json={})))
    with pytest.raises(Image3DError, match=text) as info:
        await provider.submit(b"x", "image/png")
    assert info.value.status_code == code


def _stl(mesh: trimesh.Trimesh) -> bytes:
    buf = io.BytesIO()
    mesh.export(buf, file_type="stl")
    return buf.getvalue()


def test_prepara_no_tamanho_e_apoiado_na_mesa() -> None:
    source = trimesh.creation.box((2, 1, 4))
    source.apply_translation([5, 5, 5])
    printable = prepare_for_print(_stl(source), "stl", 200)
    assert printable.watertight
    assert printable.info["bbox_mm"] == [100.0, 50.0, 200.0]
    lo, hi = printable.mesh.bounds
    assert lo[2] == pytest.approx(0)
    assert (lo[0] + hi[0]) / 2 == pytest.approx(0)
    assert printable.info["volume_cm3"] == pytest.approx(1000.0)


def test_malha_com_buraco_pequeno_e_consertada() -> None:
    mesh = trimesh.creation.icosphere(subdivisions=2)
    mesh.update_faces([i != 0 for i in range(len(mesh.faces))])
    assert not mesh.is_watertight
    assert prepare_for_print(_stl(mesh), "stl", 50).watertight


def test_modelo_vazio_recusado() -> None:
    with pytest.raises(Image3DError):
        prepare_for_print(b"solid x\nendsolid x\n", "stl", 50)
