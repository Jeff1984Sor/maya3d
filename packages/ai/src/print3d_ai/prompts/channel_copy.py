"""✍️ Redator por canal: um produto → textos para loja, Mercado Livre, Shopee e Instagram.

Só sugestão: o dono aprova cada canal. Os fatos (medidas, materiais, cores) vêm do banco;
a IA não cria números — `guards.unknown_numbers` confere depois e sinaliza o que sobrar.
Limites conservadores por canal; a integração da Fase 3 passa a ler o limite real da
categoria na API do marketplace.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

VERSION = "channel_copy/v1"
Channel = Literal["site", "mercadolivre", "shopee", "instagram"]


@dataclass(frozen=True)
class Profile:
    label: str
    title_max: int
    description_max: int
    style: str
    marketplace: bool


PROFILES: dict[str, Profile] = {
    "site": Profile(
        "Loja própria",
        120,
        2500,
        "Título claro e afetivo. Descrição em parágrafos curtos contando a história da peça, "
        "como personalizar e cuidados. Pode convidar a falar no WhatsApp da loja.",
        marketplace=False,
    ),
    "mercadolivre": Profile(
        "Mercado Livre",
        60,
        3000,
        "Título no padrão do Mercado Livre: produto + característica principal + uso, sem "
        "emojis, sem CAIXA ALTA, sem palavras promocionais (promoção, oferta, frete grátis). "
        "Descrição em texto puro, sem links, sem telefone, sem e-mail, sem redes sociais, sem "
        "citar outra loja ou WhatsApp; perguntas são respondidas pela plataforma.",
        marketplace=True,
    ),
    "shopee": Profile(
        "Shopee",
        100,
        3000,
        "Título com palavras de busca no começo (o que é + para quem/ocasião). Descrição com "
        "tópicos, sem links, sem contato externo, sem citar outras plataformas.",
        marketplace=True,
    ),
    "instagram": Profile(
        "Instagram",
        80,
        2000,
        "Legenda de post: gancho na primeira linha, história curta, chamada para o link da "
        "loja na bio. Emojis com moderação. Hashtags separadas (sem #), em português.",
        marketplace=False,
    ),
}


class ChannelCopy(BaseModel):
    channel: Channel
    title: str = Field(max_length=160, description="título/headline do canal")
    description: str = Field(max_length=3000)
    bullets: list[str] = Field(max_length=6, description="destaques curtos")
    keywords: list[str] = Field(max_length=15, description="termos de busca")
    hashtags: list[str] = Field(max_length=15, description="só instagram; sem #")


class CopySet(BaseModel):
    items: list[ChannelCopy] = Field(max_length=4)


SYSTEM = """Você é o redator da loja "{loja}" de peças impressas em 3D.
Voz da marca: {voz_marca}
Voz do nicho ({nicho}): {voz_nicho}

Regras inegociáveis:
- Português do Brasil.
- Use SOMENTE os fatos fornecidos. NUNCA invente números (medidas, peso, prazo, preço,
  quantidade, porcentagem). Se um número não estiver nos fatos, não escreva número.
- Nunca use marcas, personagens, times ou logos de terceiros; marca de carro/celular só
  como "compatível com <marca> <modelo>" se estiver nos fatos.
- Não chame de brinquedo. Não prometa resultado. Velas só LED. Recipiente de comida:
  "para alimentos embalados".
- Mencione que é feito em impressão 3D (linhas de camada podem aparecer).
- Respeite o limite de caracteres do título de cada canal.

Canais pedidos:
{canais}"""

USER = """Fatos do produto (fonte da verdade):
{fatos}

Gere um item para cada canal pedido: {lista}."""


def build(
    *,
    loja: str,
    voz_marca: str,
    nicho: str,
    voz_nicho: str,
    facts: str,
    channels: list[str],
) -> tuple[str, str]:
    canais = "\n".join(
        f"- {c} ({PROFILES[c].label}): título até {PROFILES[c].title_max} caracteres. "
        f"{PROFILES[c].style}"
        for c in channels
    )
    system = SYSTEM.format(
        loja=loja,
        voz_marca=voz_marca or "acolhedora e clara",
        nicho=nicho,
        voz_nicho=voz_nicho or "clara e objetiva",
        canais=canais,
    )
    return system, USER.format(fatos=facts, lista=", ".join(channels))
