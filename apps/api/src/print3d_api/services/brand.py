"""Leitura da marca com cache curto em memória (spec 0.1: 'editável no admin, com cache')."""

import time
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.models.brand import SINGLETON_ID, BrandSettings
from print3d_api.schemas.brand import BrandPublic


class BrandNotConfiguredError(Exception):
    pass


class BrandService:
    def __init__(self, ttl_seconds: float, clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._cached: BrandPublic | None = None
        self._expires_at = 0.0

    async def get_public(self, session: AsyncSession) -> BrandPublic:
        now = self._clock()
        if self._cached is not None and now < self._expires_at:
            return self._cached
        row = await session.get(BrandSettings, SINGLETON_ID)
        if row is None:
            raise BrandNotConfiguredError("brand_settings sem linha (rode as migrações)")
        self._cached = BrandPublic.model_validate(row)
        self._expires_at = now + self._ttl
        return self._cached

    def invalidate(self) -> None:
        """Chamado quando o admin salvar a marca."""
        self._cached = None
