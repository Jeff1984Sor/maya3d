import os
import time
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from print3d_worker.jobs import photo as photo_job


@pytest.fixture
def files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    settings = type("S", (), {"files_dir": str(tmp_path), "photo_retention_days": 30})()
    monkeypatch.setattr(photo_job, "get_worker_settings", lambda: settings)
    return tmp_path


async def test_litofania_gera_arquivos(files: Path) -> None:
    src = files / "uploads" / "fotos" / "f.png"
    src.parent.mkdir(parents=True)
    Image.linear_gradient("L").resize((120, 80)).convert("RGB").save(src)
    report = await photo_job.photo_to_part(
        {"job_id": "j1"},
        "uploads/fotos/f.png",
        "litofania",
        {"width_mm": 60, "ignorado": 1, "frame_mm": None},
    )
    out = files / "foto" / "j1"
    assert report["prefix"] == "foto/j1"
    assert (out / "completo.stl").is_file()
    assert (out / "foto.zip").is_file()
    assert report["bbox_mm"][0] == pytest.approx(60, abs=1)


async def test_cortador_de_desenho(files: Path) -> None:
    src = files / "uploads" / "fotos" / "d.png"
    src.parent.mkdir(parents=True)
    img = Image.new("RGB", (200, 200), "white")
    ImageDraw.Draw(img).ellipse([40, 40, 160, 160], fill="black")
    img.save(src)
    report = await photo_job.photo_to_part(
        {"job_id": "j2"}, "uploads/fotos/d.png", "cortador", {"size_mm": 60}
    )
    assert report["parts"][0]["name"] == "cortador"
    assert "aviso" in report["info"]


async def test_limpeza_lgpd_so_apaga_o_antigo(files: Path) -> None:
    uploads = files / "uploads" / "fotos"
    uploads.mkdir(parents=True)
    old, new = uploads / "velha.jpg", uploads / "nova.jpg"
    old.write_bytes(b"x")
    new.write_bytes(b"y")
    ancient = time.time() - 40 * 86400
    os.utime(old, (ancient, ancient))
    (files / "foto" / "j-velho").mkdir(parents=True)
    os.utime(files / "foto" / "j-velho", (ancient, ancient))
    removed = await photo_job.purge_old_photos({})
    assert removed == 2
    assert not old.exists()
    assert new.exists()
    assert not (files / "foto" / "j-velho").exists()
