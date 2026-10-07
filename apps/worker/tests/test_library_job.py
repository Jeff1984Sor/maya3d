import json
from pathlib import Path

import pytest
import trimesh

from print3d_worker.jobs import library as library_job


async def test_processa_envios(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        library_job, "get_worker_settings", lambda: type("S", (), {"files_dir": str(tmp_path)})()
    )
    inbox = tmp_path / "library" / "terco" / "_envios"
    inbox.mkdir(parents=True)
    trimesh.creation.box((50, 20, 5)).export(inbox / "terço.stl")

    out = await library_job.process_library({}, "terco", [256, 256, 256])

    assert out == {"status": "pronto", "models": 1}
    manifest = json.loads((tmp_path / "library" / "terco" / "colecao.json").read_text())
    assert manifest["status"] == "pronto"
    assert manifest["models"][0]["fits"] is True
    assert not inbox.exists()  # envios processados são apagados


async def test_sem_envios_registra_erro(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        library_job, "get_worker_settings", lambda: type("S", (), {"files_dir": str(tmp_path)})()
    )
    out = await library_job.process_library({}, "vazia", [256, 256, 256])
    assert out["status"] == "erro"
    manifest = json.loads((tmp_path / "library" / "vazia" / "colecao.json").read_text())
    assert "nenhum arquivo" in manifest["error"]
