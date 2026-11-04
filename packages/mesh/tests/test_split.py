import pytest
import trimesh

from print3d_mesh.split import SplitError, SplitOptions, plan_split, split_mesh

BED = (256.0, 256.0, 256.0)


def test_plano_cabe_sem_cortar() -> None:
    plan = plan_split((200, 100, 50), SplitOptions(bed_mm=BED))
    assert plan.counts == (1, 1, 1)


def test_plano_usa_menos_pedacos() -> None:
    plan = plan_split((500, 100, 50), SplitOptions(bed_mm=BED))
    assert plan.pieces == 2
    assert plan.counts == (2, 1, 1)


def test_plano_aproveita_rotacao() -> None:
    # 300 x 240 x 20: girando na mesa ainda precisa de 2, nunca 4
    assert plan_split((300, 240, 20), SplitOptions(bed_mm=BED)).pieces == 2
    # peça "deitável": 380 de comprimento com mesa 256 → 2 pedaços
    assert plan_split((380, 380, 380), SplitOptions(bed_mm=BED)).pieces == 8


def test_grande_demais() -> None:
    with pytest.raises(SplitError):
        plan_split((10_000, 10_000, 10_000), SplitOptions(bed_mm=BED))


def test_divide_caixa_com_pinos() -> None:
    mesh = trimesh.creation.box((500, 100, 60))
    result = split_mesh(mesh, SplitOptions(bed_mm=BED))
    assert len(result.pieces) == 2
    assert all(p.fits for p in result.pieces)
    assert all(p.mesh.is_watertight for p in result.pieces)
    assert len(result.pins) >= 1
    # furos tiram material: soma dos pedaços menor que o original
    total = sum(p.mesh.volume for p in result.pieces)
    assert total < mesh.volume
    assert total > mesh.volume * 0.98


def test_peca_oca_so_poe_pino_no_material() -> None:
    # tubo grosso: o furo do meio não pode receber pino
    tube = trimesh.creation.annulus(r_min=40, r_max=60, height=500, sections=64)
    result = split_mesh(tube, SplitOptions(bed_mm=BED, max_pins_per_face=4))
    assert len(result.pieces) == 2
    assert all(p.mesh.is_watertight for p in result.pieces)
    assert len(result.pins) >= 1


def test_malha_aberta_recusada() -> None:
    mesh = trimesh.creation.box((500, 100, 60))
    mesh.update_faces([i != 0 for i in range(len(mesh.faces))])
    with pytest.raises(SplitError, match="aberta"):
        split_mesh(mesh, SplitOptions(bed_mm=BED))


def _halteres() -> trimesh.Trimesh:
    """Dois blocos ligados por uma barra fina: o lugar certo de cortar é a barra."""
    a = trimesh.creation.box(bounds=[[0, 0, 0], [200, 100, 100]])
    bar = trimesh.creation.box(bounds=[[199, 40, 40], [301, 60, 60]])
    b = trimesh.creation.box(bounds=[[300, 0, 0], [500, 100, 100]])
    return a.union([bar, b], engine="manifold")


def test_corte_inteligente_escolhe_a_menor_emenda() -> None:
    mesh = _halteres()
    smart = split_mesh(mesh, SplitOptions(bed_mm=(400, 400, 400), label_joints=False))
    cut = smart.cuts[0][0]
    assert 200 < cut < 300  # cortou na barra fina
    assert smart.seam_area_mm2 < 500  # 20 x 20 = 400 mm², não 100 x 100
    naive = split_mesh(
        mesh, SplitOptions(bed_mm=(400, 400, 400), smart_cuts=False, label_joints=False)
    )
    assert naive.cuts[0] == [250.0]
    assert len(smart.pieces) == len(naive.pieces) == 2


def test_protege_o_topo() -> None:
    tall = trimesh.creation.box(bounds=[[0, 0, 0], [80, 80, 500]])
    result = split_mesh(
        tall, SplitOptions(bed_mm=(300, 300, 300), protect_top_pct=45, label_joints=False)
    )
    assert all(c <= 500 * 0.55 + 1e-6 for c in result.cuts[2])
    assert not any("topo" in w for w in result.warnings)


def test_protecao_impossivel_avisa() -> None:
    tall = trimesh.creation.box(bounds=[[0, 0, 0], [80, 80, 500]])
    result = split_mesh(
        tall, SplitOptions(bed_mm=(300, 300, 300), protect_top_pct=60, label_joints=False)
    )
    assert any("topo" in w for w in result.warnings)
    assert len(result.pieces) == 2


def test_etiquetas_nas_duas_faces() -> None:
    def fake_text(label: str) -> trimesh.Trimesh:
        letter = trimesh.creation.box((4, 4, 0.6))
        letter.apply_translation([0, 0, 0.3])  # de z=0 a z=0,6, como o OpenSCAD gera
        return letter

    mesh = trimesh.creation.box((500, 100, 60))
    plain = split_mesh(mesh, SplitOptions(bed_mm=BED, label_joints=False))
    labeled = split_mesh(mesh, SplitOptions(bed_mm=BED), text_factory=fake_text)
    assert labeled.labels == ["A"]
    assert all(p.mesh.is_watertight for p in labeled.pieces)
    for a, b in zip(plain.pieces, labeled.pieces, strict=True):
        assert b.mesh.volume < a.mesh.volume  # cada lado ganhou a letra gravada


def test_sem_openscad_avisa_que_nao_ha_etiqueta() -> None:
    result = split_mesh(trimesh.creation.box((500, 100, 60)), SplitOptions(bed_mm=BED))
    assert any("etiquetas" in w for w in result.warnings)


def test_letras_reais_com_openscad() -> None:
    from print3d_mesh.parametric import OpenScadRunner
    from print3d_mesh.split_labels import openscad_text_factory

    runner = OpenScadRunner()
    if not runner.available():
        pytest.skip("OpenSCAD não instalado (roda no CI)")
    factory = openscad_text_factory(runner, size_mm=5, depth_mm=0.6)
    assert factory is not None
    letter = factory("A")
    assert letter.is_watertight
    assert letter.bounds[0][2] >= -1e-6
    assert letter.bounds[1][2] == pytest.approx(0.6, abs=1e-3)
    result = split_mesh(trimesh.creation.box((500, 100, 60)), SplitOptions(bed_mm=BED), factory)
    assert result.labels == ["A"]
    assert all(p.mesh.is_watertight for p in result.pieces)


def test_escala_para_altura_final() -> None:
    # caixa de 100 mm de altura pedida com 600 mm: escala 6x e precisa de cortes na altura
    mesh = trimesh.creation.box((50, 50, 100))
    result = split_mesh(mesh, SplitOptions(bed_mm=BED, target_size_mm=600, label_joints=False))
    assert result.scale == 6.0
    assert result.size_mm == (300.0, 300.0, 600.0)
    assert result.plan.counts[2] >= 3
    assert all(p.fits for p in result.pieces)


def test_escala_pelo_maior_lado() -> None:
    mesh = trimesh.creation.box((200, 50, 20))
    options = SplitOptions(bed_mm=BED, target_size_mm=100, target_dim="maior")
    result = split_mesh(mesh, options)
    assert result.scale == 0.5
    assert len(result.pieces) == 1


def test_macho_femea_reserva_mesa_para_o_pino() -> None:
    # 2 x 250 + 8 mm de pino macho não cabe em 256 - 3 de folga: precisa de 3 pedaços
    mesh = trimesh.creation.box((500, 100, 60))
    options = SplitOptions(bed_mm=BED, connector="macho_femea", label_joints=False)
    assert len(split_mesh(mesh, options).pieces) == 3


def test_macho_femea_prende_o_pino_num_lado() -> None:
    mesh = trimesh.creation.box((480, 100, 60))
    options = SplitOptions(
        bed_mm=BED, connector="macho_femea", label_joints=False, smart_cuts=False
    )
    result = split_mesh(mesh, options)
    assert len(result.pieces) == 2
    assert result.pins == []  # nada solto para imprimir
    assert all(p.mesh.is_watertight and p.fits for p in result.pieces)
    first, second = sorted(result.pieces, key=lambda p: p.mesh.bounds[0][0])
    # o de baixo ganha o macho (passa do corte); o de cima perde material (furo)
    assert first.mesh.bounds[1][0] > second.mesh.bounds[0][0] + 5
    assert first.mesh.volume > mesh.volume / 2
    assert second.mesh.volume < mesh.volume / 2
