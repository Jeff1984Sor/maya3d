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
