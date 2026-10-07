from unittest.mock import AsyncMock

from print3d_worker.healthcheck import is_fresh
from print3d_worker.jobs.system import HEARTBEAT_KEY, heartbeat, ping


async def test_ping() -> None:
    assert await ping({}) == "pong"


async def test_heartbeat_grava_no_redis_com_ttl() -> None:
    redis = AsyncMock()
    now = await heartbeat({"redis": redis})
    redis.set.assert_awaited_once()
    args, kwargs = redis.set.await_args
    assert args[0] == HEARTBEAT_KEY
    assert float(args[1]) == now
    assert kwargs["ex"] > 0


def test_is_fresh() -> None:
    assert is_fresh(b"1000.0", now=1100.0)
    assert not is_fresh(b"1000.0", now=1200.0)  # velho demais
    assert not is_fresh(None, now=1000.0)  # sem heartbeat
    assert not is_fresh("lixo", now=1000.0)
    assert not is_fresh("2000.0", now=1000.0)  # relógio no futuro
