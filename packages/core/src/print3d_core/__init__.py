"""Domínio compartilhado entre API, worker e pacotes de integração."""

from print3d_core.channels import SalesChannel
from print3d_core.niches import NICHE_TARGETS, Niche
from print3d_core.security import TokenVault, TokenVaultError

__all__ = ["NICHE_TARGETS", "Niche", "SalesChannel", "TokenVault", "TokenVaultError"]
