"""📷 Produto pela foto: a IA com visão diz O QUE a peça é (tipo) e escreve título e texto.

Medidas NÃO vêm da IA: o tipo escolhe o tamanho numa tabela fixa (SIZES) e gramas/tempo vêm
do volume medido da malha. Assim um arquivo mal nomeado ("crucifix") que na foto é uma
medalha vira "Medalha de São Bento", com tamanho e preço de medalha.
"""

from typing import Literal

from pydantic import BaseModel, Field

VERSION = "product_from_photo/v1"

Kind = Literal[
    "medalha",
    "chaveiro",
    "pingente",
    "marcador",
    "imagem_santo",
    "cruz",
    "placa_quadro",
    "presepio",
    "infantil",
    "decoracao",
]

# Tamanho (maior medida, mm) por tipo: P, M, G. Tabela do negócio, nunca da IA.
SIZES: dict[str, tuple[int, int, int]] = {
    "medalha": (40, 50, 70),
    "chaveiro": (40, 50, 70),
    "pingente": (30, 40, 55),
    "marcador": (120, 150, 180),
    "imagem_santo": (100, 150, 200),
    "cruz": (100, 150, 200),
    "placa_quadro": (100, 150, 200),
    "presepio": (80, 120, 180),
    "infantil": (70, 100, 140),
    "decoracao": (80, 120, 160),
}


class PhotoProduct(BaseModel):
    kind: Kind = Field(description="o que a peça é, pela foto")
    title: str = Field(
        max_length=70,
        description="título curto e vendedor; nome do santo/tema; sem 'impressão 3D'",
    )
    description: str = Field(max_length=900, description="2 a 4 frases, tom acolhedor")
    tags: list[str] = Field(max_length=10)


SYSTEM = """Você cataloga peças religiosas impressas em 3D para a loja "{loja}".
Olhe a FOTO e diga o que a peça é de verdade (o nome do arquivo pode estar errado).

Regras:
- Identifique o santo, a devoção ou o tema quando der (ex.: Medalha de São Bento,
  Nossa Senhora Aparecida, Anjo da Guarda, Sagrado Coração de Jesus).
- Título curto (até 60 caracteres), sem "impressão 3D", "peça religiosa", "3D" ou marcas.
- Não invente medidas, peso, preço ou prazo. Não chame de brinquedo.
- Velas: só "para vela LED". Português do Brasil."""

USER = """Nome atual (pode estar errado): "{titulo}"
Coleção: {colecao}
Classifique a peça da foto e escreva título, descrição e tags."""


def build(*, loja: str, titulo: str, colecao: str) -> tuple[str, str]:
    return SYSTEM.format(loja=loja), USER.format(titulo=titulo, colecao=colecao)
