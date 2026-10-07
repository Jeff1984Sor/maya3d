"""Imagens nos dois fornecedores (formato oficial de cada SDK) e a regra do Guardião visual."""

import base64
from types import SimpleNamespace
from typing import Any

from pydantic import BaseModel, SecretStr

from print3d_ai import AISettings, ImageInput
from print3d_ai.claude import ClaudeProvider
from print3d_ai.openai_provider import OpenAIProvider
from print3d_ai.prompts.guardian_visual import Finding, VisualVerdict, build, decide


class Out(BaseModel):
    ok: bool


IMG = ImageInput(b"\x00\x01webp", "image/webp")
B64 = base64.standard_b64encode(IMG.data).decode()


async def test_claude_envia_bloco_de_imagem() -> None:
    calls: list[dict[str, Any]] = []

    async def parse(**kwargs: Any) -> SimpleNamespace:
        calls.append(kwargs)
        return SimpleNamespace(
            parsed_output=Out(ok=True),
            stop_reason="end_turn",
            content=[],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1),
        )

    client = SimpleNamespace(messages=SimpleNamespace(parse=parse))
    provider = ClaudeProvider(AISettings(api_key=SecretStr("k")), client=client)
    await provider.complete_json(system="s", prompt="olhe", schema=Out, model="m", images=[IMG])
    content = calls[0]["messages"][0]["content"]
    assert content[0] == {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/webp", "data": B64},
    }
    assert content[-1] == {"type": "text", "text": "olhe"}


async def test_openai_envia_data_url() -> None:
    calls: list[dict[str, Any]] = []

    async def parse(**kwargs: Any) -> SimpleNamespace:
        calls.append(kwargs)
        message = SimpleNamespace(parsed=Out(ok=True), refusal=None, content="{}")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message)],
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1),
        )

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=parse)))
    provider = OpenAIProvider(AISettings(api_key=SecretStr("k")), client=client)
    await provider.complete_json(system="s", prompt="olhe", schema=Out, model="m", images=[IMG])
    user = calls[0]["messages"][1]["content"]
    assert user[0] == {"type": "text", "text": "olhe"}
    assert user[1]["image_url"]["url"] == f"data:image/webp;base64,{B64}"


def test_regra_de_bloqueio() -> None:
    def verdict(*f: Finding) -> VisualVerdict:
        return VisualVerdict(findings=list(f), summary="")

    assert decide(verdict()) == "ok"
    assert (
        decide(verdict(Finding(kind="personagem", description="Mickey", confidence=0.9)))
        == "bloqueado"
    )
    assert (
        decide(verdict(Finding(kind="personagem", description="parece", confidence=0.5)))
        == "alerta"
    )
    assert (
        decide(verdict(Finding(kind="qualidade", description="escura", confidence=0.9))) == "alerta"
    )
    assert decide(verdict(Finding(kind="logo", description="x", confidence=0.2))) == "ok"
    system, user = build(titulo="Terço", nicho="religioso")
    assert "santos" in system
    assert "Terço" in user
