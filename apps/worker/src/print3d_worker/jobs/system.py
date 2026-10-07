"""Jobs de sistema: prova de vida do worker."""

import time
from typing import Any

HEARTBEAT_KEY = "print3d:worker:heartbeat"
HEARTBEAT_TTL_SECONDS = 180


async def ping(ctx: dict[str, Any]) -> str:
    """Job de teste: confirma que a fila está consumindo (usado em smoke tests)."""
    return "pong"


async def heartbeat(ctx: dict[str, Any]) -> float:
    """Grava o instante atual no Redis; o healthcheck do container lê isto."""
    now = time.time()
    await ctx["redis"].set(HEARTBEAT_KEY, str(now), ex=HEARTBEAT_TTL_SECONDS)
    return now
