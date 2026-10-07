"""Importar todos os modelos aqui garante que o Alembic os enxergue em Base.metadata."""

from print3d_api.models.ai import AIConfig, ChannelCopy, ProductEmbedding
from print3d_api.models.brand import BrandSettings
from print3d_api.models.catalog import Design, Product, Variant
from print3d_api.models.content import ProductImage, StoreLayout, StorePage
from print3d_api.models.governance import AuditLog, GuardianTermOverride, License, Niche
from print3d_api.models.integrations import IntegrationSetting
from print3d_api.models.library import LibraryCollection, LibraryModel
from print3d_api.models.marketplace import ChannelAccount, ChannelListing, MarketplaceQuestion
from print3d_api.models.orders import (
    Cart,
    Customer,
    InboundMessage,
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
    "ChannelAccount",
    "ChannelCopy",
    "ChannelFeeBand",
    "ChannelListing",
    "CostConfig",
    "Customer",
    "Design",
    "GuardianTermOverride",
    "InboundMessage",
    "IntegrationSetting",
    "LibraryCollection",
    "LibraryModel",
    "License",
    "MarketplaceQuestion",
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
    "ProductEmbedding",
    "ProductImage",
    "StoreLayout",
    "StorePage",
    "Variant",
]
