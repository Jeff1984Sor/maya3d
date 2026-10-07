"""Healthcheck do container: `python -m print3d_worker.healthcheck` (exit 0 = saudável)."""

import asyncio
import sys
import time

from redis.asyncio import Redis

from print3d_worker.config import get_worker_settings
from print3d_worker.jobs.system import HEARTBEAT_KEY

MAX_AGE_SECONDS = 150.0


def is_fresh(raw: str | bytes | None, now: float, max_age: float = MAX_AGE_SECONDS) -> bool:
    if raw is None:
        return False
    try:
        beat = float(raw)
    except ValueError:
        return False
    return 0 <= now - beat <= max_age


async def check() -> bool:
    redis: Redis = Redis.from_url(get_worker_settings().redis_url)
    try:
        return is_fresh(await redis.get(HEARTBEAT_KEY), time.time())
    finally:
        await redis.aclose()


def main() -> None:
    sys.exit(0 if asyncio.run(check()) else 1)


if __name__ == "__main__":
    main()
