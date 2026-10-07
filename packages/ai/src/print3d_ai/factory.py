"""Escolhe o provedor pela configuração (AI_PROVIDER): trocar de fornecedor sem mudar código."""

from collections.abc import Sequence
from typing import Protocol, TypeVar

from pydantic import BaseModel

from print3d_ai.claude import AINotConfiguredError, ClaudeProvider
from print3d_ai.config import AISettings
from print3d_ai.openai_provider import OpenAIProvider
from print3d_ai.providers import ImageInput

T = TypeVar("T", bound=BaseModel)
PROVIDERS = ("claude", "openai")


class ChatProvider(Protocol):
    async def complete_json(
        self,
        *,
        system: str,
        prompt: str,
        schema: type[T],
        model: str,
        max_tokens: int = 8000,
        images: Sequence[ImageInput] = (),
    ) -> T: ...

    async def list_models(self) -> list[str]: ...


def make_provider(settings: AISettings) -> ChatProvider:
    if settings.provider == "claude":
        return ClaudeProvider(settings)
    if settings.provider == "openai":
        return OpenAIProvider(settings)
    raise AINotConfiguredError(f"AI_PROVIDER desconhecido: {settings.provider} (use {PROVIDERS})")
