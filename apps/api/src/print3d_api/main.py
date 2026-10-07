"""Fábrica da aplicação FastAPI."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from print3d_api.config import Settings, get_settings
from print3d_api.db.session import create_engine, create_session_factory
from print3d_api.health import HealthChecker
from print3d_api.logging import configure_logging
from print3d_api.middleware import RequestContextMiddleware
from print3d_api.routes import brand, health
from print3d_api.services.brand import BrandService

log = logging.getLogger("print3d.api")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(settings)
        redis: Redis = Redis.from_url(settings.redis_url)
        app.state.session_factory = create_session_factory(engine)
        app.state.health_checker = HealthChecker(engine, redis)
        log.info("api iniciada", extra={"release": settings.release, "env": settings.environment})
        try:
            yield
        finally:
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
    return app
