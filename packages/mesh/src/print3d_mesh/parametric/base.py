"""Base dos modelos paramétricos: parâmetros validados por Pydantic → código SCAD por parte
(uma parte por cor, para impressão multicor) → STL → checagens de imprimibilidade."""

from abc import ABC, abstractmethod
from typing import ClassVar

import trimesh
from pydantic import BaseModel


class ParametricModel[P: BaseModel](ABC):
    slug: ClassVar[str]
    title: ClassVar[str]
    niche: ClassVar[str]
    description: ClassVar[str]
    params_model: ClassVar[type[BaseModel]]

    @abstractmethod
    def parts(self, params: P) -> list[str]:
        """Nomes das partes (cada uma vira um STL / uma cor)."""

    @abstractmethod
    def scad(self, params: P, part: str) -> str:
        """Código OpenSCAD completo de uma parte."""

    def check(self, params: P, meshes: dict[str, trimesh.Trimesh]) -> list[str]:
        """Checagens depois de gerar (legibilidade, peças soltas...). Lista de problemas."""
        return []

    def parse(self, raw: dict[str, object]) -> P:
        return self.params_model.model_validate(raw)  # type: ignore[return-value]
