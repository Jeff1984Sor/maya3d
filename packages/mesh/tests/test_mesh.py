from pathlib import Path

from print3d_mesh import MeshAnalyzer, MeshReport, Slicer, SliceResult


class _Analyzer:
    def analyze(self, path: Path) -> MeshReport:
        return MeshReport(bbox_mm=(1, 2, 3), volume_mm3=6, watertight=True)


class _Slicer:
    def slice(self, model_path: Path, *, profile: str) -> SliceResult:
        return SliceResult(grams_by_color={"pla-branco": 12.5}, print_seconds=3600, profile=profile)


def test_fakes_satisfazem_contratos() -> None:
    assert isinstance(_Analyzer(), MeshAnalyzer)
    assert isinstance(_Slicer(), Slicer)
