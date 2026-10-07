"""Provedor OpenAI (SDK oficial `openai`). Saída validada por Pydantic via
`chat.completions.parse(response_format=Schema)`; mesmo contrato do ClaudeProvider."""

import logging
import time
from typing import Any, TypeVar

import openai
from pydantic import BaseModel, ValidationError

from print3d_ai.claude import AINotConfiguredError, AIOutputError, AIRefusedError
from print3d_ai.config import AISettings

T = TypeVar("T", bound=BaseModel)
log = logging.getLogger("print3d.ai")


class OpenAIProvider:
    def __init__(self, settings: AISettings, client: Any | None = None) -> None:
        if client is None:
            if settings.api_key is None or not settings.api_key.get_secret_value():
                raise AINotConfiguredError("IA não configurada: defina AI_API_KEY no .env")
            client = openai.AsyncOpenAI(api_key=settings.api_key.get_secret_value())
        self._client = client

    async def list_models(self) -> list[str]:
        page = await self._client.models.list()
        return sorted(m.id for m in page.data)

    async def complete_json(
        self, *, system: str, prompt: str, schema: type[T], model: str, max_tokens: int = 8000
    ) -> T:
        messages: list[Any] = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        for attempt in (1, 2):
            started = time.perf_counter()
            completion = await self._client.chat.completions.parse(
                model=model, messages=messages, response_format=schema
            )
            usage = completion.usage
            log.info(
                "chamada de IA",
                extra={
                    "provider": "openai",
                    "model": model,
                    "schema": schema.__name__,
                    "ms": round((time.perf_counter() - started) * 1000),
                    "input_tokens": getattr(usage, "prompt_tokens", 0),
                    "output_tokens": getattr(usage, "completion_tokens", 0),
                    "attempt": attempt,
                },
            )
            message = completion.choices[0].message
            if getattr(message, "refusal", None):
                raise AIRefusedError(f"o modelo recusou: {message.refusal}")
            try:
                if message.parsed is None:
                    raise AIOutputError("resposta sem JSON")
                return schema.model_validate(message.parsed.model_dump())
            except ValidationError as exc:
                if attempt == 2:
                    raise AIOutputError(f"saída inválida: {exc.errors()[:3]}") from exc
                messages = [
                    *messages,
                    {"role": "assistant", "content": message.content or ""},
                    {
                        "role": "user",
                        "content": "A resposta não passou na validação: "
                        f"{exc.errors(include_url=False)[:5]}. Corrija e responda de novo.",
                    },
                ]
        raise AIOutputError("sem resposta válida")
