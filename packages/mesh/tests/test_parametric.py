"""Paramétricos: validação e SCAD sempre; geração real só onde houver OpenSCAD (CI)."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from print3d_mesh.parametric import (
    FONTS,
    MODELS,
    BoxParams,
    KeychainParams,
    OpenScadRunner,
    generate,
    scad_string,
)
from print3d_mesh.parametric.fonts import FONTS_DIR

needs_openscad = pytest.mark.skipif(
    not OpenScadRunner().available(), reason="OpenSCAD não instalado (roda no CI)"
)


def test_fontes_existem_com_licenca() -> None:
    for font in FONTS.values():
        assert (FONTS_DIR / font.file).is_file(), font.file
        assert font.license == "OFL-1.1"
    assert len(list(FONTS_DIR.glob("OFL-*.txt"))) >= 5


def test_scad_string_nao_permite_injecao() -> None:
    evil = 'Ana"); cube(1000); echo("'
    literal = scad_string(evil)
    assert literal.startswith('"')
    assert literal.endswith('"')
    assert '\\"' in literal  # aspas escapadas: continua sendo uma string só
    assert "\n" not in scad_string("linha1\nlinha2")


@pytest.mark.parametrize(
    "bad",
    [
        {"letter": "AB"},
        {"letter": "#"},
        {"name": ""},
        {"name": "x" * 15},
        {"name": "Ana<script>"},
        {"style": "inicial_data", "name": "Ana"},
        {"style": "letra_nome", "letter": None},
        {"letter_size_mm": 100},
    ],
)
def test_chaveiro_rejeita_parametros_invalidos(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        KeychainParams.model_validate(bad)


def test_chaveiro_aceita_acentos_e_cedilha() -> None:
    p = KeychainParams.model_validate({"letter": "Ç", "name": "Conceição"})
    assert p.letter == "Ç"


def test_chaveiro_fontes_por_estilo() -> None:
    assert KeychainParams(style="letra_nome").fonts() == ("bold", "cursiva")
    assert KeychainParams(style="letra_cursiva_nome").fonts()[0] == "manuscrita"
    assert KeychainParams(name_font="retro").fonts()[1] == "retro"


def test_scad_do_chaveiro_tem_partes_e_fontes() -> None:
    model = MODELS["chaveiro-letra-nome"]
    params = model.parse({"letter": "J", "name": "Jefferson"})
    assert model.parts(params) == ["base", "nome"]
    src = model.scad(params, "nome")
    assert 'PART = "nome";' in src
    assert 'N = "Jefferson";' in src
    assert "use <" in src
    assert "Poppins-Bold.ttf" in src


@pytest.mark.parametrize(
    "bad",
    [
        {"corner_radius_mm": 40, "shape": "quadrada", "width_mm": 60},
        {"lip_mm": 12, "height_mm": 10},
        {"lid": "sem_tampa", "lid_text": "Ana"},
        {"width_mm": 5},
    ],
)
def test_caixa_rejeita_parametros_invalidos(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        BoxParams.model_validate(bad)


def test_caixa_redonda_ignora_profundidade_e_calcula_externa() -> None:
    p = BoxParams(shape="redonda", width_mm=50, depth_mm=80, height_mm=30)
    assert p.depth_mm == 50
    assert p.outer_mm == (54.0, 54.0, 34.0)
    assert MODELS["caixa"].parts(p) == ["caixa", "tampa"]
    assert MODELS["caixa"].parts(BoxParams(lid="sem_tampa")) == ["caixa"]


@needs_openscad
@pytest.mark.parametrize("style", ["letra_nome", "letra_cursiva_nome", "so_nome"])
@pytest.mark.parametrize("letter", ["J", "L", "O"])
def test_gera_chaveiro_imprimivel(tmp_path: Path, style: str, letter: str) -> None:
    result = generate(
        MODELS["chaveiro-letra-nome"],
        {"style": style, "letter": letter, "name": "Ana Clara"},
        tmp_path,
    )
    assert result.printable, result.issues
    assert all(r.watertight for r in result.reports.values())
    assert (tmp_path / "completo.stl").stat().st_size > 0


@needs_openscad
def test_nome_longo_demais_para_ler(tmp_path: Path) -> None:
    result = generate(
        MODELS["chaveiro-letra-nome"],
        {"letter": "I", "name": "Maximilianusss", "letter_size_mm": 25, "min_text_mm": 6},
        tmp_path,
    )
    assert any("legível" in i for i in result.issues)


@needs_openscad
@pytest.mark.parametrize("shape", ["redonda", "quadrada", "retangular", "hexagonal", "oval"])
def test_gera_caixa_com_tampa(tmp_path: Path, shape: str) -> None:
    result = generate(
        MODELS["caixa"],
        {
            "shape": shape,
            "width_mm": 60,
            "depth_mm": 40,
            "height_mm": 30,
            "dividers_x": 1,
            "lid_text": "Ana",
        },
        tmp_path,
    )
    assert result.printable, result.issues
    assert set(result.files) == {"caixa", "tampa"}
    assert all(r.watertight for r in result.reports.values())
