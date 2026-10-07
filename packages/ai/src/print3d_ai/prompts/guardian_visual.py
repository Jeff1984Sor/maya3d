"""👁️ Guardião visual: olha a foto do produto e aponta riscos de propriedade intelectual e
problemas de foto. Complementa o Guardião de texto (regras determinísticas).

A IA descreve o que vê com um grau de confiança; quem decide bloquear é o código
(`decide`), com limites fixos e auditáveis.
"""

from typing import Literal

from pydantic import BaseModel, Field

VERSION = "guardian_visual/v1"

Kind = Literal[
    "personagem",  # Disney, Marvel, Pokémon, anime, desenho
    "marca",  # marca registrada / produto de terceiro
    "logo",
    "time",  # escudo de time / seleção
    "pessoa_real",  # rosto reconhecível de pessoa real (imagem/LGPD)
    "texto_ofensivo",
    "qualidade",  # foto escura, borrada, fundo bagunçado, peça cortada
]
IP_KINDS = frozenset({"personagem", "marca", "logo", "time"})
BLOCK_AT = 0.75  # confiança mínima para bloquear sozinho
ALERT_AT = 0.4


class Finding(BaseModel):
    kind: Kind
    description: str = Field(max_length=300, description="o que foi visto, em português")
    confidence: float = Field(ge=0, le=1)


class VisualVerdict(BaseModel):
    findings: list[Finding] = Field(max_length=10)
    summary: str = Field(max_length=400, description="resumo curto para o dono")


SYSTEM = """Você é o Guardião visual de uma loja de peças impressas em 3D. Analise a foto do
produto e aponte SOMENTE o que você realmente vê.

Procure:
- personagem de terceiros (Disney, Marvel, DC, Pokémon, anime, desenhos, games);
- marca, logo ou produto de terceiro (exceto acessório "compatível com" um aparelho);
- escudo de time ou seleção;
- rosto reconhecível de pessoa real (famoso ou não);
- texto ofensivo;
- qualidade da foto: escura, borrada, fundo bagunçado, peça cortada.

NÃO são problema: imagens religiosas tradicionais (santos, Nossa Senhora, Jesus, cruz,
anjos, presépio), letras e nomes personalizados, formas geométricas, animais genéricos.
Na dúvida, confiança baixa. Não invente: se a foto estiver limpa, findings vazio."""

USER = """Produto: "{titulo}" (nicho: {nicho}).
Analise a imagem anexada."""


def build(*, titulo: str, nicho: str) -> tuple[str, str]:
    return SYSTEM, USER.format(titulo=titulo, nicho=nicho)


def decide(verdict: VisualVerdict) -> str:
    """ok | alerta | bloqueado — regra fixa sobre o que a IA viu."""
    if any(f.kind in IP_KINDS and f.confidence >= BLOCK_AT for f in verdict.findings):
        return "bloqueado"
    if any(f.confidence >= ALERT_AT for f in verdict.findings):
        return "alerta"
    return "ok"
