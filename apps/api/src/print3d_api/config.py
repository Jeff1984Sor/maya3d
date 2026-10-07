"""Configuração via variáveis de ambiente (segredos só no .env do servidor / GitHub Secrets)."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["ci", "staging", "production"] = "ci"
    release: str = "dev"  # sha/tag da imagem, injetado no deploy
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://print3d:print3d@localhost:5432/print3d"
    redis_url: str = "redis://localhost:6379/0"
    fernet_key: SecretStr | None = None

    cors_origins: list[str] = []
    brand_cache_ttl_seconds: float = 60.0

    # Rotas /v1/admin/* exigem o header X-Admin-Token. Sem token configurado, ficam desligadas.
    admin_api_token: SecretStr | None = None
    max_upload_mb: int = 50


@lru_cache
def get_settings() -> Settings:
    return Settings()
