"""Biblioteca: organizar um acervo enviado (ZIPs, pastas numeradas, malhas soltas, imagens)."""

import zipfile
from pathlib import Path

import trimesh
from PIL import Image

from print3d_mesh.library import fits, organize, pretty_title, safe_name


def _stl(path: Path, size: tuple[float, float, float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    trimesh.creation.box(size).export(path)


def _png(path: Path, side: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (side, side), (200, 160, 60)).save(path)


def test_nomes() -> None:
    assert safe_name("gold heart keychain 3d model.STL") == "gold-heart-keychain-3d-model.stl"
    assert safe_name("ÂNGEL+DE+LA+GUARDA.3mf") == "angel-de-la-guarda.3mf"
    assert safe_name("../../etc/passwd") == "passwd"
    assert safe_name(r"x.s/t\l") == "l"
    assert safe_name("peça.ST L") == "peca.stl"
    assert pretty_title("gold heart keychain 3d model.stl") == "Gold heart keychain"
    assert fits([300, 100, 50], (256, 256, 256)) is False
    assert fits([100, 250, 50], (256, 256, 256)) is True
    assert fits(None, (256, 256, 256)) is None


def test_organiza_acervo(tmp_path: Path) -> None:
    raw, out = tmp_path / "envios", tmp_path / "modelos"
    # pastas numeradas com imagem (estilo pacote vendido)
    _stl(raw / "1" / "gold crown pendant 3d model.stl", (40, 30, 4))
    _png(raw / "1" / "1.png", 64)
    _stl(raw / "2" / "heart.stl", (300, 80, 40))  # não cabe em 256
    # malha solta na raiz + imagem
    _stl(raw / "Anjo da Guarda.stl", (90, 60, 150))
    _png(raw / "anjo.webp", 32)
    # ZIP com uma peça e uma entrada maliciosa
    zip_path = raw / "Presepio.zip"
    piece = tmp_path / "presepio.stl"
    _stl(piece, (120, 80, 90))
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.write(piece, "presepio/presepio.stl")
        zf.writestr("../../fora.stl", b"solid x\nendsolid x\n")

    result = organize(raw, out, (256, 256, 256))
    models = {m["key"]: m for m in result["models"]}

    assert not (tmp_path.parent / "fora.stl").exists()
    assert any("perigoso" in w for w in result["warnings"])
    crown = models["gold-crown-pendant-3d-model"]
    assert crown["title"] == "Gold crown pendant"
    assert crown["cover"] == "1.png"
    assert (out / crown["key"] / crown["cover"]).is_file()
    assert crown["fits"] is True
    assert crown["bbox_mm"] == [40.0, 30.0, 4.0]
    assert models["heart"]["fits"] is False
    assert models["anjo-da-guarda"]["cover"] == "anjo.webp"
    assert "presepio" in models
    assert all((out / k).is_dir() for k in models)

    # novo envio soma, sem sobrescrever as pastas existentes
    raw2 = tmp_path / "envios2"
    _stl(raw2 / "heart.stl", (10, 10, 10))
    again = organize(raw2, out, (256, 256, 256))
    assert again["models"][0]["key"] != "heart"
    assert (out / "heart" / "heart.stl").is_file()
