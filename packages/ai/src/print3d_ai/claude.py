"""Provedor Claude (SDK oficial `anthropic`). Saída sempre validada por Pydantic via
`messages.parse` (structured outputs); uma nova tentativa com o erro de validação quando o
JSON respeita o schema mas falha em regras extras do modelo Pydantic (limites, padrões).
"""

import logging
import time
from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from print3d_ai.config import AISettings

T = TypeVar("T", bound=BaseModel)
log = logging.getLogger("print3d.ai")


class AINotConfiguredError(Exception):
    """Sem chave/modelo no ambiente: o recurso de IA fica desligado, nada quebra."""


class AIRefusedError(Exception):
    """O modelo recusou (stop_reason = refusal)."""


class AIOutputError(Exception):
    """Saída inválida mesmo após a nova tentativa."""


class ClaudeProvider:
    def __init__(self, settings: AISettings, client: Any | None = None) -> None:
        if client is None:
            if settings.api_key is None or not settings.api_key.get_secret_value():
                raise AINotConfiguredError("IA não configurada: cole a chave em Integrações")
            client = anthropic.AsyncAnthropic(api_key=settings.api_key.get_secret_value())
        self._client = client
        self._settings = settings

    async def list_models(self) -> list[str]:
        page = await self._client.models.list()
        return sorted(m.id for m in page.data)

    async def complete_json(
        self, *, system: str, prompt: str, schema: type[T], model: str, max_tokens: int = 8000
    ) -> T:
        messages: list[Any] = [{"role": "user", "content": prompt}]
        for attempt in (1, 2):
            started = time.perf_counter()
            response = await self._client.messages.parse(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                output_format=schema,
            )
            usage = response.usage
            log.info(
                "chamada de IA",
                extra={
                    "model": model,
                    "schema": schema.__name__,
                    "ms": round((time.perf_counter() - started) * 1000),
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cache_read_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
                    "stop_reason": response.stop_reason,
                    "attempt": attempt,
                },
            )
            if response.stop_reason == "refusal":
                raise AIRefusedError("o modelo recusou o pedido")
            try:
                parsed = response.parsed_output
                if parsed is None:
                    raise AIOutputError("resposta sem JSON")
                return schema.model_validate(parsed.model_dump())
            except ValidationError as exc:
                if attempt == 2:
                    raise AIOutputError(f"saída inválida: {exc.errors()[:3]}") from exc
                messages = [
                    *messages,
                    {"role": "assistant", "content": response.content},
                    {
                        "role": "user",
                        "content": "A resposta não passou na validação: "
                        f"{exc.errors(include_url=False)[:5]}. Corrija e responda de novo.",
                    },
                ]
        raise AIOutputError("sem resposta válida")
