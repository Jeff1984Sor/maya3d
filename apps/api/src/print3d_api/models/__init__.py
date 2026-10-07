"""Importar todos os modelos aqui garante que o Alembic os enxergue em Base.metadata."""

from print3d_api.models.brand import BrandSettings
from print3d_api.models.catalog import Design, Product, Variant
from print3d_api.models.pricing import ChannelFeeBand, CostConfig
from print3d_api.models.production import Material, PackagingBox, Printer

__all__ = [
    "BrandSettings",
    "ChannelFeeBand",
    "CostConfig",
    "Design",
    "Material",
    "PackagingBox",
    "Printer",
    "Product",
    "Variant",
]
