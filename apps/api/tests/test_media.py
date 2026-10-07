"""Imagens da loja: regravadas em WebP, sem metadados, com miniatura; lixo é recusado."""

import io
from pathlib import Path

import pytest
from PIL import Image

from print3d_api.services import media
from print3d_core.storage import LocalStorage


def _jpeg(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    exif = Image.Exif()
    exif[0x010F] = "Celular X"  # fabricante: não pode sobrar na foto publicada
    Image.new("RGB", (w, h), (10, 120, 200)).save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def test_regrava_em_webp_com_miniatura(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    saved = media.save_image(storage, _jpeg(3000, 2000), folder="produtos/1")
    assert saved.key.startswith("media/produtos/1/")
    assert saved.key.endswith(".webp")
    full = Image.open(storage.local_path(saved.key))
    thumb = Image.open(storage.local_path(saved.thumb_key))
    assert full.format == "WEBP"
    assert max(full.size) == media.FULL_SIDE
    assert max(thumb.size) == media.THUMB_SIDE
    assert not full.getexif()
    assert media.public_url(saved.key) == f"/m/{saved.key}"


def test_recusa_arquivo_que_nao_e_imagem(tmp_path: Path) -> None:
    with pytest.raises(media.MediaError):
        media.save_image(LocalStorage(tmp_path), b"<script>alert(1)</script>")


def test_apaga_so_dentro_de_media(tmp_path: Path) -> None:
    storage = LocalStorage(tmp_path)
    other = tmp_path / "library" / "x.stl"
    other.parent.mkdir(parents=True)
    other.write_text("x")
    media.delete(storage, "library/x.stl", None)
    assert other.exists()
