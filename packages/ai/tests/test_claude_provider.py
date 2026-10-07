"""ClaudeProvider sem rede: cliente falso imitando `messages.parse` do SDK."""

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, Field, SecretStr

from print3d_ai import (
    AINotConfiguredError,
    AIOutputError,
    AIRefusedError,
    AISettings,
    ClaudeProvider,
    LLMProvider,
)
from print3d_ai.prompts import enrich_product


class Out(BaseModel):
    title: str = Field(max_length=10)


def _response(parsed: Any, stop: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(
        parsed_output=parsed,
        stop_reason=stop,
        content=[],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0),
    )


class FakeMessages:
    def __init__(self, responses: list[SimpleNamespace]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    async def parse(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return self.responses.pop(0)


def _provider(*responses: SimpleNamespace) -> tuple[ClaudeProvider, FakeMessages]:
    messages = FakeMessages(list(responses))
    return ClaudeProvider(AISettings(), client=SimpleNamespace(messages=messages)), messages


def test_sem_chave_fica_desligado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_API_KEY", raising=False)
    with pytest.raises(AINotConfiguredError):
        ClaudeProvider(AISettings())


def test_com_chave_cria_cliente() -> None:
    assert isinstance(ClaudeProvider(AISettings(api_key=SecretStr("sk-test"))), LLMProvider)


async def test_saida_valida() -> None:
    provider, messages = _provider(_response(Out(title="ok")))
    out = await provider.complete_json(system="s", prompt="p", schema=Out, model="m")
    assert out.title == "ok"
    assert messages.calls[0]["output_format"] is Out
    assert messages.calls[0]["model"] == "m"


async def test_recusa() -> None:
    provider, _ = _provider(_response(None, stop="refusal"))
    with pytest.raises(AIRefusedError):
        await provider.complete_json(system="s", prompt="p", schema=Out, model="m")


async def test_tenta_de_novo_com_o_erro_e_desiste_na_segunda() -> None:
    long = SimpleNamespace(model_dump=lambda: {"title": "longo demais aqui"})
    provider, messages = _provider(_response(long), _response(Out(title="curto")))
    out = await provider.complete_json(system="s", prompt="p", schema=Out, model="m")
    assert out.title == "curto"
    assert "validação" in messages.calls[1]["messages"][-1]["content"]

    provider, _ = _provider(_response(long), _response(long))
    with pytest.raises(AIOutputError):
        await provider.complete_json(system="s", prompt="p", schema=Out, model="m")


def test_prompt_de_enriquecer_tem_as_regras() -> None:
    system, user = enrich_product.build(
        loja="Loja X",
        voz_marca="",
        nicho="religioso",
        voz_nicho="reverente",
        dica="Nossa Senhora Aparecida 15cm manto azul",
        categoria=None,
    )
    assert "NUNCA invente números" in system
    assert "Loja X" in system
    assert "reverente" in system
    assert "Aparecida" in user
