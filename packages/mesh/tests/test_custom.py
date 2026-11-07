from pathlib import Path

import pytest
import trimesh

from print3d_mesh.custom import CustomPart, CustomScadError, generate_custom, validate
from print3d_mesh.parametric import OpenScadRunner

needs_openscad = pytest.mark.skipif(
    not OpenScadRunner().available(), reason="OpenSCAD não instalado (roda no CI)"
)

BASE = "cube([100, 6, 50]);\ntranslate([40, -14, 0]) cube([20, 34, 4]);"
TEXT = (
    "translate([50, 0, 30]) rotate([90, 0, 0]) linear_extrude(1)\n"
    '  text("Café", size=10, font="Poppins:style=Bold", halign="center");'
)


def test_valida_e_devolve_textos_para_o_guardiao() -> None:
    texts = validate([CustomPart("base", BASE), CustomPart("texto", TEXT)])
    assert texts == ["Café"]


@pytest.mark.parametrize(
    "scad",
    [
        "include <segredo.scad>",
        "use </etc/passwd>",
        'import("/srv/print3d/prod/.env");',
        'surface(file="x.dat");',
    ],
)
def test_nao_le_arquivos(scad: str) -> None:
    with pytest.raises(CustomScadError, match="sem ler arquivos"):
        validate([CustomPart("base", scad)])


def test_fonte_fora_da_lista_recusada() -> None:
    with pytest.raises(CustomScadError, match="fonte"):
        validate([CustomPart("t", 'text("Oi", font="Comic Sans MS");')])


def test_nomes_e_quantidade_de_partes() -> None:
    with pytest.raises(CustomScadError):
        validate([])
    with pytest.raises(CustomScadError, match="nomes"):
        validate([CustomPart("Base!", BASE)])
    with pytest.raises(CustomScadError, match="nomes"):
        validate([CustomPart("a", BASE), CustomPart("a", BASE)])
    with pytest.raises(CustomScadError, match="grande"):
        validate([CustomPart("a", "cube(1);" * 3000)])


@needs_openscad
def test_gera_partes_conjunto_e_3mf(tmp_path: Path) -> None:
    result = generate_custom([CustomPart("base", BASE), CustomPart("texto", TEXT)], tmp_path)
    assert result["files"] == {"base": "base.stl", "texto": "texto.stl"}
    assert result["bbox_mm"][0] == pytest.approx(100, abs=0.5)
    scene = trimesh.load(tmp_path / "projeto.3mf")
    assert isinstance(scene, trimesh.Scene)
    assert len(scene.geometry) == 2
    assert result["source"]["base"] == BASE


@needs_openscad
def test_codigo_com_erro_vira_mensagem(tmp_path: Path) -> None:
    with pytest.raises(Exception, match="OpenSCAD"):
        generate_custom([CustomPart("base", "cube([10, 10, 10]")], tmp_path)
