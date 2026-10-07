"""Checagens de prontidão (usadas por docker healthcheck, nginx e smoke tests)."""

from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass(frozen=True)
class CheckResult:
    ok: bool
    detail: str = ""


class HealthChecker:
    def __init__(self, engine: AsyncEngine, redis: Redis) -> None:
        self._engine = engine
        self._redis = redis

    async def run(self) -> dict[str, CheckResult]:
        return {"database": await self._database(), "redis": await self._redis_ping()}

    async def _database(self) -> CheckResult:
        try:
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as exc:
            return CheckResult(False, type(exc).__name__)
        return CheckResult(True)

    async def _redis_ping(self) -> CheckResult:
        try:
            await self._redis.ping()
        except Exception as exc:
            return CheckResult(False, type(exc).__name__)
        return CheckResult(True)
