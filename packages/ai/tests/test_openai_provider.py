"""OpenAIProvider e fábrica, sem rede (cliente falso imitando o SDK)."""

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, Field, SecretStr

from print3d_ai import AINotConfiguredError, AIOutputError, AIRefusedError, AISettings
from print3d_ai.claude import ClaudeProvider
from print3d_ai.factory import make_provider
from print3d_ai.openai_provider import OpenAIProvider


class Out(BaseModel):
    title: str = Field(max_length=10)


def _completion(parsed: Any, refusal: str | None = None) -> SimpleNamespace:
    message = SimpleNamespace(parsed=parsed, refusal=refusal, content="{}")
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message)],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5),
    )


class FakeCompletions:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def parse(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return self.responses.pop(0)


def _provider(*responses: SimpleNamespace) -> tuple[OpenAIProvider, FakeCompletions]:
    completions = FakeCompletions(list(responses))
    models = SimpleNamespace(
        list=lambda: _async(
            SimpleNamespace(data=[SimpleNamespace(id="b"), SimpleNamespace(id="a")])
        )
    )
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions), models=models)
    return OpenAIProvider(AISettings(), client=client), completions


async def _async(value: Any) -> Any:
    return value


async def test_saida_valida_e_system_no_inicio() -> None:
    provider, completions = _provider(_completion(Out(title="ok")))
    out = await provider.complete_json(system="regras", prompt="p", schema=Out, model="m")
    assert out.title == "ok"
    assert completions.calls[0]["response_format"] is Out
    assert completions.calls[0]["messages"][0] == {"role": "system", "content": "regras"}


async def test_recusa() -> None:
    provider, _ = _provider(_completion(None, refusal="não posso"))
    with pytest.raises(AIRefusedError):
        await provider.complete_json(system="s", prompt="p", schema=Out, model="m")


async def test_nova_tentativa_e_desistencia() -> None:
    long = SimpleNamespace(model_dump=lambda: {"title": "longo demais aqui"})
    provider, _ = _provider(_completion(long), _completion(long))
    with pytest.raises(AIOutputError):
        await provider.complete_json(system="s", prompt="p", schema=Out, model="m")


async def test_lista_modelos_da_conta() -> None:
    provider, _ = _provider()
    assert await provider.list_models() == ["a", "b"]


def test_fabrica_escolhe_pelo_ambiente() -> None:
    key = SecretStr("sk-test")
    assert isinstance(make_provider(AISettings(provider="openai", api_key=key)), OpenAIProvider)
    assert isinstance(make_provider(AISettings(provider="claude", api_key=key)), ClaudeProvider)
    with pytest.raises(AINotConfiguredError):
        make_provider(AISettings(provider="outro", api_key=key))
