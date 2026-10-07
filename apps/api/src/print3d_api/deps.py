"""Dependências FastAPI. Tudo vem de app.state para ser trocável nos testes."""

from fastapi import Request

from print3d_api.config import Settings
from print3d_api.health import HealthChecker
from print3d_api.services.brand import BrandService


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_health_checker(request: Request) -> HealthChecker:
    checker: HealthChecker = request.app.state.health_checker
    return checker


def get_brand_service(request: Request) -> BrandService:
    service: BrandService = request.app.state.brand_service
    return service
