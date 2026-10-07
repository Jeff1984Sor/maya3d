"""Dependências FastAPI. Tudo vem de app.state para ser trocável nos testes."""

from pathlib import Path

from arq.connections import ArqRedis
from fastapi import Request

from print3d_api.config import Settings
from print3d_api.health import HealthChecker
from print3d_api.services import ai, search
from print3d_api.services.brand import BrandService
from print3d_core.storage import LocalStorage


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_health_checker(request: Request) -> HealthChecker:
    checker: HealthChecker = request.app.state.health_checker
    return checker


def get_brand_service(request: Request) -> BrandService:
    service: BrandService = request.app.state.brand_service
    return service


def get_queue(request: Request) -> ArqRedis:
    """Fila de jobs (arq) — render, fatiamento, paramétricos, publicação."""
    queue: ArqRedis = request.app.state.queue
    return queue


def get_storage(request: Request) -> LocalStorage:
    settings: Settings = request.app.state.settings
    return LocalStorage(Path(settings.files_dir))


def get_ai_factory(request: Request) -> ai.ProviderFactory:
    """Fornecedor de IA (trocável nos testes por app.state.ai_factory)."""
    factory: ai.ProviderFactory = getattr(request.app.state, "ai_factory", ai.default_factory)
    return factory


def get_embedder_factory(request: Request) -> search.EmbedderFactory:
    factory: search.EmbedderFactory = getattr(
        request.app.state, "embedder_factory", search.default_embedder_factory
    )
    return factory
