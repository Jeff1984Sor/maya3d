"""Modelos de IA por tarefa vêm do ambiente — nunca hardcoded (spec seção 1)."""

from enum import StrEnum

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AITask(StrEnum):
    DEFAULT = "default"  # tarefas simples e baratas
    GUARDIAN = "guardian"  # Guardião de IP: modelo forte
    PERSONALIZER = "personalizer"  # personalizador por linguagem natural: modelo forte
    EMBEDDING = "embedding"


class AISettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AI_", extra="ignore")

    provider: str = "claude"  # claude | gemini
    api_key: SecretStr | None = None
    model_default: str | None = None
    model_guardian: str | None = None
    model_personalizer: str | None = None
    model_embedding: str | None = None
    daily_budget_usd: float = 5.0  # limite diário por agente (spec seção 7)

    def model_for(self, task: AITask) -> str:
        value = getattr(self, f"model_{task.value}")
        if not value:
            raise RuntimeError(f"AI_MODEL_{task.name} não configurado no ambiente")
        return str(value)
