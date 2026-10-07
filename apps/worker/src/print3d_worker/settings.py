"""Entrada do arq: `arq print3d_worker.settings.ArqSettings`."""

import logging
from typing import Any, ClassVar

from arq import cron
from arq.connections import RedisSettings

from print3d_worker.config import get_worker_settings
from print3d_worker.jobs.system import heartbeat, ping

log = logging.getLogger("print3d.worker")


async def on_startup(ctx: dict[str, Any]) -> None:
    await heartbeat(ctx)
    log.info("worker iniciado")


async def on_shutdown(ctx: dict[str, Any]) -> None:
    log.info("worker encerrando")


class ArqSettings:
    functions: ClassVar[list[Any]] = [ping]
    cron_jobs: ClassVar[list[Any]] = [cron(heartbeat, second=0)]  # todo minuto
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings.from_dsn(get_worker_settings().redis_url)
    max_jobs = 4
    job_timeout = 600
    keep_result = 3600
