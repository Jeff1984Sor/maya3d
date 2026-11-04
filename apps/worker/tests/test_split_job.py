import itertools
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
    # projeto .3mf: um objeto por pedaço + pinos, todos no chão e sem sobrepor
    assert "pecas.3mf" in names
    scene = trimesh.load(out / "pecas.3mf")
    assert isinstance(scene, trimesh.Scene)
    assert len(scene.geometry) == len(report["pieces"]) + 1
    bounds = [g.bounds for g in scene.dump()]
    assert all(abs(b[0][2]) < 1e-6 for b in bounds)
    xs = sorted((b[0][0], b[1][0]) for b in bounds)
    assert all(a[1] <= b[0] for a, b in itertools.pairwise(xs))


async def test_escala_e_macho_femea(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        split_job, "get_worker_settings", lambda: type("S", (), {"files_dir": str(tmp_path)})()
    )
    src = tmp_path / "uploads" / "peca.stl"
    src.parent.mkdir(parents=True)
    trimesh.creation.box((40, 40, 100)).export(src)

    report = await split_job.split_model(
        {"job_id": "j2"},
        "uploads/peca.stl",
        {
            "bed_mm": [256, 256, 256],
            "target_size_mm": 400,
            "connector": "macho_femea",
            "label_joints": False,
        },
    )
    assert report["scale"] == 4.0
    assert report["size_mm"] == [160.0, 160.0, 400.0]
    assert len(report["pieces"]) == 2
    assert report["pins"] == {"count": 0, "file": None}
    assert (tmp_path / "split" / "j2" / "pecas.3mf").is_file()
