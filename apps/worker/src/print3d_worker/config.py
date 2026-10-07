from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "INFO"
    release: str = "dev"
    files_dir: str = "/data/files"  # volume compartilhado com a API


@lru_cache
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()
