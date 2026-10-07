import io

import pytest
import trimesh

from print3d_mesh import MeshAnalysisError, MeshAnalyzer, TrimeshAnalyzer, fits_build_volume


def _stl(mesh: trimesh.Trimesh) -> bytes:
    buf = io.BytesIO()
    mesh.export(buf, file_type="stl")
    return buf.getvalue()


def test_caixa_fechada() -> None:
    report = TrimeshAnalyzer().analyze_bytes(_stl(trimesh.creation.box((20, 30, 40))), "stl")
    assert sorted(report.bbox_mm) == [20, 30, 40]
    assert report.volume_mm3 == pytest.approx(24000, rel=1e-6)
    assert report.watertight
    assert report.issues == []
    assert report.triangles == 12


def test_malha_aberta_e_sinalizada() -> None:
    box = trimesh.creation.box((10, 10, 10))
    box.update_faces([i != 0 for i in range(len(box.faces))])  # remove uma face
    report = TrimeshAnalyzer().analyze_bytes(_stl(box), "stl")
    assert not report.watertight
    assert report.volume_mm3 == 0
    assert any("malha aberta" in i for i in report.issues)


def test_unidade_suspeita() -> None:
    report = TrimeshAnalyzer().analyze_bytes(_stl(trimesh.creation.box((0.05, 0.05, 0.05))), "stl")
    assert any("unidade" in i for i in report.issues)


def test_formato_nao_suportado() -> None:
    with pytest.raises(MeshAnalysisError, match="não suportado"):
        TrimeshAnalyzer().analyze_bytes(b"x", "step")


def test_arquivo_lixo() -> None:
    with pytest.raises(MeshAnalysisError):
        TrimeshAnalyzer().analyze_bytes(b"isto nao e um stl", "stl")


def test_satisfaz_contrato() -> None:
    assert isinstance(TrimeshAnalyzer(), MeshAnalyzer)


@pytest.mark.parametrize(
    ("bbox", "bed", "cabe"),
    [
        ((100, 100, 100), (256, 256, 256), True),
        ((250, 100, 50), (256, 256, 256), True),
        ((255, 100, 50), (256, 256, 256), False),  # folga de 2 mm
        ((300, 50, 50), (256, 256, 256), False),
        ((200, 170, 20), (180, 180, 250), True),  # deitando a peça ela cabe
    ],
)
def test_cabe_na_mesa(
    bbox: tuple[float, float, float], bed: tuple[float, float, float], cabe: bool
) -> None:
    assert fits_build_volume(bbox, bed) is cabe
