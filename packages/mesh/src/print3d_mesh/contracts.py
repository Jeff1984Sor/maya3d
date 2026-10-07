"""Contratos do pipeline 3D. Gramas e tempo vêm SEMPRE do fatiador, nunca de estimativa."""

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field


class MeshReport(BaseModel):
    bbox_mm: tuple[float, float, float]
    volume_mm3: float = Field(ge=0)
    area_mm2: float = Field(ge=0, default=0)
    triangles: int = Field(ge=0, default=0)
    watertight: bool
    min_wall_mm: float | None = None
    issues: list[str] = []


class SliceResult(BaseModel):
    grams_by_color: dict[str, float]  # chave: id do material/cor
    print_seconds: int = Field(ge=0)
    profile: str  # perfil de impressora/filamento usado


@runtime_checkable
class MeshAnalyzer(Protocol):
    def analyze(self, path: Path) -> MeshReport: ...


@runtime_checkable
class Slicer(Protocol):
    def slice(self, model_path: Path, *, profile: str) -> SliceResult: ...
