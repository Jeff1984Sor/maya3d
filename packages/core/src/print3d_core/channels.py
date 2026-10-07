"""Canais de venda suportados."""

from enum import StrEnum


class SalesChannel(StrEnum):
    MERCADO_LIVRE = "mercadolivre"
    SHOPEE = "shopee"
    SITE = "site"

    @property
    def is_marketplace(self) -> bool:
        """Marketplaces proíbem comunicação fora da plataforma (spec seção 2)."""
        return self is not SalesChannel.SITE
