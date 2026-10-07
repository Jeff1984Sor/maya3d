"""Contratos de IA. Implementações concretas (Claude, Gemini) entram na Fase 2."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class ImageInput:
    """Imagem enviada junto do pedido (Guardião visual). media_type: image/webp, image/png..."""

    data: bytes
    media_type: str = "image/webp"


@runtime_checkable
class LLMProvider(Protocol):
    """Saída sempre JSON validado por Pydantic (retry com correção fica na implementação)."""

    async def complete_json(
        self, *, system: str, prompt: str, schema: type[T], model: str
    ) -> T: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Vetores para busca semântica. A dimensão depende do modelo escolhido no painel."""

    async def embed(self, texts: Sequence[str], *, model: str) -> list[list[float]]: ...
