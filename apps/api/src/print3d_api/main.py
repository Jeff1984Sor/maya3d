"""Fábrica da aplicação FastAPI."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from print3d_api.config import Settings, get_settings
from print3d_api.db.session import create_engine, create_session_factory
from print3d_api.dispatcher import run_dispatcher
from print3d_api.health import HealthChecker
from print3d_api.logging import configure_logging
from print3d_api.middleware import RequestContextMiddleware
from print3d_api.routes import admin, brand, channels, health, store, webhooks
from print3d_api.services import search
from print3d_api.services.brand import BrandService
from print3d_notify.meta import WhatsAppSettings

log = logging.getLogger("print3d.api")


def create_app(
    settings: Settings | None = None, whatsapp: WhatsAppSettings | None = None
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings)
        redis: Redis = Redis.from_url(settings.redis_url)
        app.state.session_factory = create_session_factory(engine)
        app.state.health_checker = HealthChecker(engine, redis)
        app.state.queue = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        dispatcher: asyncio.Task[None] | None = None
        app.state.dispatch_now = asyncio.Event()
        if settings.environment != "ci":  # liga sozinho quando o WhatsApp for configurado
            dispatcher = asyncio.create_task(
                run_dispatcher(
                    app.state.session_factory, app.state.whatsapp, app.state.dispatch_now
                )
            )
        indexer: asyncio.Task[None] | None = None
        if settings.environment != "ci":  # mantém a busca semântica em dia (liga sozinho)
            indexer = asyncio.create_task(
                search.run_indexer(
                    app.state.session_factory, search.default_embedder_factory, interval=300
                )
            )
        log.info("api iniciada", extra={"release": settings.release, "env": settings.environment})
        try:
            yield
        finally:
            for task in (dispatcher, indexer):
                if task is not None:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
            await app.state.queue.aclose()
            await redis.aclose()
            await engine.dispose()

    configure_logging(settings.log_level)
    app = FastAPI(
        title="Print3D API",
        version=settings.release,
        lifespan=lifespan,
        # Documentação interativa só fora de produção.
        docs_url=None if settings.environment == "production" else "/docs",
        redoc_url=None,
        openapi_url=None if settings.environment == "production" else "/openapi.json",
    )
    app.state.settings = settings
    app.state.whatsapp = whatsapp or WhatsAppSettings()
    app.state.brand_service = BrandService(settings.brand_cache_ttl_seconds)

    app.add_middleware(RequestContextMiddleware)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["*"],
            allow_credentials=True,
        )

    app.include_router(health.router)
    app.include_router(brand.router)
    app.include_router(admin.router)
    app.include_router(store.router)
    app.include_router(webhooks.router)
    app.include_router(channels.router)
    return app
