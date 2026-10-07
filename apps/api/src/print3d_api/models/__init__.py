"""Importar todos os modelos aqui garante que o Alembic os enxergue em Base.metadata."""

from print3d_api.models.ai import AIConfig
from print3d_api.models.brand import BrandSettings
from print3d_api.models.catalog import Design, Product, Variant
from print3d_api.models.governance import AuditLog, GuardianTermOverride, License, Niche
from print3d_api.models.orders import (
    Cart,
    Customer,
    Notification,
    OpsConfig,
    Order,
    OrderEvent,
    OrderItem,
    PrintJob,
    ProducedFingerprint,
)
from print3d_api.models.pricing import ChannelFeeBand, CostConfig
from print3d_api.models.production import Material, PackagingBox, Printer

__all__ = [
    "AIConfig",
    "AuditLog",
    "BrandSettings",
    "Cart",
    "ChannelFeeBand",
    "CostConfig",
    "Customer",
    "Design",
    "GuardianTermOverride",
    "License",
    "Material",
    "Niche",
    "Notification",
    "OpsConfig",
    "Order",
    "OrderEvent",
    "OrderItem",
    "PackagingBox",
    "PrintJob",
    "Printer",
    "ProducedFingerprint",
    "Product",
    "Variant",
]
