"""Embeddings para a busca semântica (SDK oficial `openai`: `embeddings.create`)."""

import logging
import time
from collections.abc import Sequence
from typing import Any

import openai

from print3d_ai.claude import AINotConfiguredError
from print3d_ai.config import AISettings

log = logging.getLogger("print3d.ai")
BATCH = 64


class OpenAIEmbeddings:
    def __init__(self, api_key: str, client: Any | None = None) -> None:
        self._client = client or openai.AsyncOpenAI(api_key=api_key)

    async def embed(self, texts: Sequence[str], *, model: str) -> list[list[float]]:
        out: list[list[float]] = []
        for start in range(0, len(texts), BATCH):
            chunk = list(texts[start : start + BATCH])
            began = time.perf_counter()
            res = await self._client.embeddings.create(model=model, input=chunk)
            log.info(
                "embeddings",
                extra={
                    "model": model,
                    "n": len(chunk),
                    "ms": round((time.perf_counter() - began) * 1000),
                    "input_tokens": getattr(res.usage, "prompt_tokens", 0),
                },
            )
            out.extend(list(d.embedding) for d in sorted(res.data, key=lambda d: d.index))
        return out


def embedding_backend(settings: AISettings) -> tuple[str | None, str | None]:
    """(fornecedor, chave) efetivos para embeddings."""
    provider = settings.embedding_provider or ("openai" if settings.provider == "openai" else None)
    key = settings.embedding_api_key or (
        settings.api_key if provider == settings.provider else None
    )
    return provider, key.get_secret_value() if key and key.get_secret_value() else None


def make_embedder(settings: AISettings) -> OpenAIEmbeddings:
    provider, key = embedding_backend(settings)
    if provider != "openai":
        raise AINotConfiguredError("busca por significado precisa de chave OpenAI (Integrações)")
    if not key:
        raise AINotConfiguredError("busca por significado sem chave (Integrações)")
    return OpenAIEmbeddings(key)
