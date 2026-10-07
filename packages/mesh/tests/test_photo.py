"""Foto vira peça com imagens sintéticas (sem arquivos externos)."""

import io

import numpy as np
import pytest
from PIL import Image, ImageDraw

from print3d_mesh.photo import (
    PhotoError,
    cookie_cutter,
    heightfield_mesh,
    lithophane,
    load_image,
    multicolor_plate,
    silhouette_keychain,
)


def _gradient() -> Image.Image:
    arr = np.tile(np.linspace(0, 255, 200, dtype=np.uint8), (100, 1))
    return Image.fromarray(arr).convert("RGB")


def _heart() -> Image.Image:
    """Forma escura sobre fundo claro (como um desenho em papel)."""
    img = Image.new("RGB", (300, 300), "white")
    d = ImageDraw.Draw(img)
    d.ellipse([40, 60, 160, 180], fill="black")
    d.ellipse([140, 60, 260, 180], fill="black")
    d.polygon([(50, 140), (250, 140), (150, 270)], fill="black")
    return img


def _four_colors() -> Image.Image:
    img = Image.new("RGB", (200, 200), "#FFFFFF")
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 99, 99], fill="#FF0000")
    d.rectangle([100, 0, 199, 99], fill="#0000FF")
    d.rectangle([0, 100, 99, 199], fill="#000000")
    return img


def test_mapa_de_alturas_fechado() -> None:
    mesh = heightfield_mesh(np.full((20, 30), 2.0), pitch_mm=1.0)
    assert mesh.is_watertight
    assert mesh.volume == pytest.approx(19 * 29 * 2.0, rel=1e-6)


def test_litofania_escuro_mais_grosso() -> None:
    result = lithophane(_gradient(), width_mm=60, frame_mm=0)
    mesh = result.combined
    assert mesh.is_watertight
    x0, _, _ = mesh.bounds[0]
    x1, _, _ = mesh.bounds[1]
    assert x1 - x0 == pytest.approx(60, abs=1)
    # lado esquerdo (preto) mais grosso que o direito (branco)
    left = mesh.vertices[mesh.vertices[:, 0] < x0 + 5][:, 2].max()
    right = mesh.vertices[mesh.vertices[:, 0] > x1 - 5][:, 2].max()
    assert left > right + 1.5


def test_litofania_espessuras_invalidas() -> None:
    with pytest.raises(PhotoError):
        lithophane(_gradient(), min_mm=3, max_mm=1)


def test_placa_multicor_faixas_por_cor() -> None:
    result = multicolor_plate(_four_colors(), width_mm=50, colors=4, pitch_mm=0.5)
    assert result.combined.is_watertight
    assert len(result.parts) == 4
    assert all(p.is_watertight for p in result.parts.values())
    bands = result.info["faixas"]
    assert isinstance(bands, list)
    assert bands[0]["cor"] == "#FFFFFF"  # mais clara na base
    assert bands[-1]["cor"] == "#000000"  # mais escura no topo
    assert result.info["trocar_filamento_em_mm"] == [1.0, 1.6, 2.2]


def test_cortador_de_biscoito() -> None:
    result = cookie_cutter(_heart(), size_mm=70)
    mesh = result.combined
    assert mesh.is_watertight
    assert max(mesh.extents[:2]) == pytest.approx(70 + 2 * (1.2 + 3.0), abs=2)
    assert mesh.extents[2] == pytest.approx(12, abs=0.01)


def test_chaveiro_de_silhueta_com_furo() -> None:
    result = silhouette_keychain(_heart(), size_mm=45)
    mesh = result.combined
    assert mesh.is_watertight
    assert mesh.extents[2] == pytest.approx(4, abs=0.01)
    assert mesh.euler_number < 2  # tem furo (genus ≥ 1)


def test_imagem_em_branco_nao_tem_forma() -> None:
    with pytest.raises(PhotoError):
        cookie_cutter(Image.new("RGB", (100, 100), "white"), size_mm=50, invert=True)


def test_carrega_png_e_rejeita_lixo() -> None:
    buf = io.BytesIO()
    _heart().save(buf, format="PNG")
    assert load_image(buf.getvalue()).size == (300, 300)
    with pytest.raises(PhotoError):
        load_image(b"nao e imagem")
