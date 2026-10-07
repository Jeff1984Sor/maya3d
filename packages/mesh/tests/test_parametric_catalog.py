"""Modelos novos (cruz, placa, lembrancinha, suporte): validação e SCAD sempre; geração
real e checagens de imprimibilidade onde houver OpenSCAD (CI)."""

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from print3d_mesh.parametric import MODELS, OpenScadRunner, generate
from print3d_mesh.parametric.cross import CrossParams
from print3d_mesh.parametric.plaque import PlaqueParams, TagParams
from print3d_mesh.parametric.stand import StandParams
from print3d_mesh.parametric.text import fit_size, legibility_issue

needs_openscad = pytest.mark.skipif(
    not OpenScadRunner().available(), reason="OpenSCAD não instalado (roda no CI)"
)


def test_catalogo_de_modelos() -> None:
    assert {"cruz-nome", "placa-nome", "lembrancinha-tag", "suporte-celular"} <= set(MODELS)
    assert MODELS["cruz-nome"].text_fields == ("name", "date")
    assert MODELS["suporte-celular"].text_fields == ()
    for model in MODELS.values():
        schema = model.params_model.model_json_schema()
        assert schema["properties"], model.slug


def test_tamanho_de_texto_cabe() -> None:
    assert fit_size("Ana", 100, 20, "bold") == 20  # limitado pela altura
    long = fit_size("Maria Eduarda Silva", 60, 20, "bold")
    assert long * 0.74 * 19 <= 60.01
    assert legibility_issue("x", 2, 3.5) is not None
    assert legibility_issue("x", 10, 3.5) is None


@pytest.mark.parametrize(
    ("cls", "bad"),
    [
        (CrossParams, {"name": ""}),
        (CrossParams, {"name": "<script>"}),
        (CrossParams, {"date": "amanhã"}),
        (CrossParams, {"height_mm": 500}),
        (PlaqueParams, {"line1": "x" * 25}),
        (PlaqueParams, {"mount": "cola"}),
        (TagParams, {"shape": "quadrado"}),
        (TagParams, {"name": 'Ana"); cube(1000); //'}),
        (StandParams, {"phone_mm": 40}),
        (StandParams, {"width_mm": 50, "cable_slot": True}),
    ],
)
def test_rejeita_parametros_invalidos(cls: Any, bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        cls.model_validate(bad)


def test_partes_por_opcao() -> None:
    cruz = MODELS["cruz-nome"]
    assert cruz.parts(CrossParams(finish="pe")) == ["cruz", "texto", "pe"]
    assert cruz.parts(CrossParams(finish="pendurar")) == ["cruz", "texto"]
    assert MODELS["placa-nome"].parts(PlaqueParams(mount="furos")) == ["placa", "texto"]
    p = PlaqueParams(line1="Escritório", line2="Dra. Ana Souza")
    assert p.height_mm > PlaqueParams(line1="Escritório").height_mm
    assert p.size2() < p.size1()


def test_scad_escapa_texto_e_usa_fonte() -> None:
    model = MODELS["lembrancinha-tag"]
    params = model.parse({"name": "Lívia", "detail": "1 aninho"})
    src = model.scad(params, "texto")
    assert 'N = "Lívia";' in src
    assert 'X = "1 aninho";' in src
    assert "Pacifico" in src


def test_suporte_base_cobre_o_encosto() -> None:
    p = StandParams(angle_deg=55, back_mm=120, phone_mm=15)
    assert p.base_mm > 15 + 120 * 0.57
    src = MODELS["suporte-celular"].scad(p, "suporte")
    assert "CABLE = true;" in src


CASES = [
    ("cruz-nome", {"name": "Miguel", "date": "12/10/2026", "finish": "pe"}),
    ("cruz-nome", {"name": "Maria Clara", "finish": "pendurar", "edge": "reta"}),
    ("placa-nome", {"line1": "Sala da Ana", "line2": "Nutricionista", "mount": "pe"}),
    ("placa-nome", {"line1": "Escritório", "shape": "oval", "frame": False}),
    ("lembrancinha-tag", {"name": "Helena", "detail": "1 aninho", "shape": "coracao"}),
    ("lembrancinha-tag", {"name": "Theo", "shape": "estrela"}),
    ("lembrancinha-tag", {"name": "Bento", "detail": "batizado", "shape": "circulo"}),
    ("suporte-celular", {}),
    ("suporte-celular", {"angle_deg": 75, "cable_slot": False, "phone_mm": 9}),
]


@needs_openscad
@pytest.mark.parametrize(("slug", "params"), CASES)
def test_gera_imprimivel(tmp_path: Path, slug: str, params: dict[str, Any]) -> None:
    result = generate(MODELS[slug], params, tmp_path)
    assert result.printable, result.issues
    assert all(r.watertight for r in result.reports.values()), result.reports
    assert min(result.bbox_mm[:2]) > 10


@needs_openscad
def test_suporte_fica_em_pe(tmp_path: Path) -> None:
    result = generate(MODELS["suporte-celular"], {}, tmp_path)
    import trimesh

    mesh = trimesh.load(tmp_path / result.files["suporte"], force="mesh")
    assert mesh.bounds[0][1] >= -0.01  # nada abaixo da mesa (perfil no plano XY)
