"""Domínio compartilhado entre API, worker e pacotes de integração."""

from print3d_core.channels import SalesChannel
from print3d_core.niches import NICHE_TARGETS, Niche
from print3d_core.pricing import (
    ChannelQuote,
    CostBreakdown,
    CostInputs,
    FeeBand,
    PricingError,
    ProfitRule,
    compute_cost,
    quote_channel,
)
from print3d_core.security import TokenVault, TokenVaultError

__all__ = [
    "NICHE_TARGETS",
    "ChannelQuote",
    "CostBreakdown",
    "CostInputs",
    "FeeBand",
    "Niche",
    "PricingError",
    "ProfitRule",
    "SalesChannel",
    "TokenVault",
    "TokenVaultError",
    "compute_cost",
    "quote_channel",
]
