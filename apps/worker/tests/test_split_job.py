import json
import zipfile
from pathlib import Path

import pytest
import trimesh

from print3d_worker.jobs import split as split_job


async def test_divide_e_empacota(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        split_job, "get_worker_settings", lambda: type("S", (), {"files_dir": str(tmp_path)})()
    )
    src = tmp_path / "uploads" / "peca.stl"
    src.parent.mkdir(parents=True)
    trimesh.creation.box((500, 120, 60)).export(src)

    report = await split_job.split_model(
        {"job_id": "j1"}, "uploads/peca.stl", {"bed_mm": [256, 256, 256]}
    )

    out = tmp_path / "split" / "j1"
    assert report["prefix"] == "split/j1"
    assert len(report["pieces"]) == 2
    assert all(p["fits"] for p in report["pieces"])
    assert report["pins"]["count"] >= 1
    for name in ("explodido.stl", "pinos.stl", "pecas.zip", "relatorio.json"):
        assert (out / name).is_file(), name
    with zipfile.ZipFile(out / "pecas.zip") as zf:
        names = set(zf.namelist())
    assert {p["file"] for p in report["pieces"]} | {"pinos.stl", "relatorio.json"} <= names
    assert json.loads((out / "relatorio.json").read_text())["plan"]["counts"] == [2, 1, 1]
