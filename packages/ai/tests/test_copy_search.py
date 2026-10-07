"""Redator por canal, assistente, embeddings e conferências — sem rede."""

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import SecretStr

from print3d_ai import AINotConfiguredError, AISettings
from print3d_ai.embeddings import OpenAIEmbeddings, embedding_backend, make_embedder
from print3d_ai.guards import contact_info, unknown_numbers
from print3d_ai.prompts import channel_copy, shop_assistant


class FakeEmbeddingsAPI:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        data = [
            SimpleNamespace(index=i, embedding=[float(len(t)), 1.0])
            for i, t in reversed(list(enumerate(kwargs["input"])))
        ]
        return SimpleNamespace(data=data, usage=SimpleNamespace(prompt_tokens=3))


async def test_embeddings_em_lotes_e_ordem() -> None:
    api = FakeEmbeddingsAPI()
    emb = OpenAIEmbeddings("k", client=SimpleNamespace(embeddings=api))
    texts = ["a" * (i + 1) for i in range(70)]
    vectors = await emb.embed(texts, model="modelo-x")
    assert [v[0] for v in vectors] == [float(i + 1) for i in range(70)]
    assert [len(c["input"]) for c in api.calls] == [64, 6]
    assert api.calls[0]["model"] == "modelo-x"


def test_fornecedor_de_embeddings() -> None:
    openai_cfg = AISettings(provider="openai", api_key=SecretStr("k"))
    assert embedding_backend(openai_cfg) == ("openai", "k")
    claude = AISettings(provider="claude", api_key=SecretStr("c"))
    assert embedding_backend(claude) == (None, None)
    with pytest.raises(AINotConfiguredError):
        make_embedder(claude)
    mixed = claude.model_copy(
        update={"embedding_provider": "openai", "embedding_api_key": SecretStr("o")}
    )
    assert embedding_backend(mixed) == ("openai", "o")
    sem_chave = claude.model_copy(update={"embedding_provider": "openai"})
    with pytest.raises(AINotConfiguredError):
        make_embedder(sem_chave)


def test_numeros_inventados() -> None:
    facts = "Tamanho: 15 cm x 8,5 cm. Material: PLA."
    assert unknown_numbers("Peça de 15 cm e 8.5 cm, impressão 3D", facts) == []
    assert unknown_numbers("Pronta em 2 dias, pesa 40 g", facts) == ["2", "40"]


def test_contato_externo() -> None:
    assert contact_info("Chame no WhatsApp (15) 99999-0000 ou www.loja.com") != []
    assert contact_info("Chaveiro personalizado com nome, feito em impressão 3D") == []


def test_prompts() -> None:
    system, user = channel_copy.build(
        loja="Loja",
        voz_marca="",
        nicho="Religioso",
        voz_nicho="",
        facts="Título: Terço",
        channels=["mercadolivre", "instagram"],
    )
    assert "até 60 caracteres" in system
    assert "Instagram" in system
    assert "mercadolivre, instagram" in user
    turns = [shop_assistant.ChatTurn(role="user", content="presente para madrinha")]
    system, user = shop_assistant.build(
        loja="Loja", voz_marca="", candidates=[("terco", "Terço", "religioso", True)], turns=turns
    )
    assert "terco | Terço | religioso | sim" in user
    assert "Cliente: presente para madrinha" in user
    _, empty = shop_assistant.build(loja="L", voz_marca="", candidates=[], turns=turns)
    assert "nenhum produto" in empty
