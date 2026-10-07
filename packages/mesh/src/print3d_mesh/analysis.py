"""Análise de malha com trimesh: medidas, volume, fechamento e se cabe na impressora.

Não estima gramas nem tempo (isso é do fatiador). Unidades: o STL não carrega unidade;
assumimos milímetros, que é o padrão dos fatiadores.
"""

import io
from pathlib import Path
from typing import Final

import trimesh

from print3d_mesh.contracts import MeshReport

SUPPORTED_TYPES: Final = frozenset({"stl", "obj", "ply"})
# Menor que isso provavelmente foi exportado em metros/polegadas ou é lixo.
_TINY_MM: Final = 1.0
# Maior que isso não cabe em impressora desktop alguma: provável unidade errada.
_HUGE_MM: Final = 2000.0


class MeshAnalysisError(Exception):
    pass


class TrimeshAnalyzer:
    def analyze(self, path: Path) -> MeshReport:
        return self.analyze_bytes(path.read_bytes(), path.suffix.lstrip(".").lower())

    def analyze_bytes(self, data: bytes, file_type: str) -> MeshReport:
        file_type = file_type.lower()
        if file_type not in SUPPORTED_TYPES:
            raise MeshAnalysisError(f"formato não suportado: {file_type} (use STL, OBJ ou PLY)")
        try:
            mesh = trimesh.load(io.BytesIO(data), file_type=file_type, force="mesh")
        except Exception as exc:
            raise MeshAnalysisError(f"arquivo ilegível: {exc}") from exc
        if not isinstance(mesh, trimesh.Trimesh) or len(mesh.faces) == 0:
            raise MeshAnalysisError("arquivo sem malha")
        return _report(mesh)


def _report(mesh: trimesh.Trimesh) -> MeshReport:
    x, y, z = (round(float(v), 2) for v in mesh.extents)
    issues: list[str] = []
    watertight = bool(mesh.is_watertight)
    if not watertight:
        issues.append("malha aberta: precisa de reparo antes de fatiar")
    if not mesh.is_winding_consistent:
        issues.append("normais inconsistentes")
    if min(x, y, z) < _TINY_MM:
        issues.append("peça com dimensão < 1 mm: confira a unidade de exportação")
    if max(x, y, z) > _HUGE_MM:
        issues.append("peça com mais de 2 m: provável unidade errada (polegadas/cm)")
    # Volume só é confiável em malha fechada.
    volume = abs(float(mesh.volume)) if watertight else 0.0
    return MeshReport(
        bbox_mm=(x, y, z),
        volume_mm3=round(volume, 2),
        area_mm2=round(float(mesh.area), 2),
        triangles=len(mesh.faces),
        watertight=watertight,
        issues=issues,
    )


def fits_build_volume(
    bbox_mm: tuple[float, float, float],
    build_mm: tuple[float, float, float],
    *,
    margin_mm: float = 2.0,
) -> bool:
    """Cabe na mesa em alguma orientação? Compara dimensões ordenadas, com folga de borda."""
    part = sorted(bbox_mm)
    bed = sorted(b - margin_mm for b in build_mm)
    return all(p <= b for p, b in zip(part, bed, strict=True))
