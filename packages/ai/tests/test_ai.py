from collections.abc import Sequence

import pytest
from pydantic import BaseModel

from print3d_ai import AISettings, AITask, EmbeddingProvider, LLMProvider


class _Out(BaseModel):
    ok: bool


class _FakeLLM:
    async def complete_json(
        self, *, system: str, prompt: str, schema: type[_Out], model: str
    ) -> _Out:
        return schema(ok=True)


class _FakeEmbed:
    async def embed(self, texts: Sequence[str], *, model: str) -> list[list[float]]:
        return [[0.0, 0.0, 0.0] for _ in texts]


def test_fakes_satisfazem_os_contratos() -> None:
    assert isinstance(_FakeLLM(), LLMProvider)
    assert isinstance(_FakeEmbed(), EmbeddingProvider)


def test_modelo_nao_configurado_falha_alto(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_MODEL_GUARDIAN", raising=False)
    with pytest.raises(RuntimeError, match="GUARDIAN"):
        AISettings().model_for(AITask.GUARDIAN)


def test_modelo_vem_do_ambiente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_MODEL_DEFAULT", "modelo-x")
    assert AISettings().model_for(AITask.DEFAULT) == "modelo-x"
