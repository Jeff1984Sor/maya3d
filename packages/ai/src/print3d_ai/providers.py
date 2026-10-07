"""Contratos de IA. Implementações concretas (Claude, Gemini) entram na Fase 2."""

from collections.abc import Sequence
from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class LLMProvider(Protocol):
    """Saída sempre JSON validado por Pydantic (retry com correção fica na implementação)."""

    async def complete_json(
        self, *, system: str, prompt: str, schema: type[T], model: str
    ) -> T: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    dimensions: int

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...
