"""Entrada do arq: `arq print3d_worker.settings.ArqSettings`."""

import logging
from typing import Any, ClassVar

from arq import cron, func
from arq.connections import RedisSettings

from print3d_worker.config import get_worker_settings
from print3d_worker.jobs.library import process_library
from print3d_worker.jobs.parametric import generate_parametric
from print3d_worker.jobs.photo import photo_to_part, purge_old_photos
from print3d_worker.jobs.split import split_model
from print3d_worker.jobs.system import heartbeat, ping

log = logging.getLogger("print3d.worker")


async def on_startup(ctx: dict[str, Any]) -> None:
    await heartbeat(ctx)
    log.info("worker iniciado")


async def on_shutdown(ctx: dict[str, Any]) -> None:
    log.info("worker encerrando")


class ArqSettings:
    functions: ClassVar[list[Any]] = [
        ping,
        generate_parametric,
        split_model,
        photo_to_part,
        func(process_library, timeout=2 * 3600, max_tries=1),  # acervo grande: muitos STL
    ]
    cron_jobs: ClassVar[list[Any]] = [
        cron(heartbeat, second=0),  # todo minuto
        cron(purge_old_photos, hour=4, minute=10),  # LGPD, diário
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = RedisSettings.from_dsn(get_worker_settings().redis_url)
    max_jobs = 4
    job_timeout = 600
    keep_result = 3600
