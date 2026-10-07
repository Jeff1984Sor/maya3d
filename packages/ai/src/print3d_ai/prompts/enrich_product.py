"""✨ Enriquecer produto (spec 5.5): poucas palavras → título, descrição, categoria, tags, FAQ, SEO.

A IA NUNCA inventa números: medidas, peso, gramas, tempo e preço vêm do pipeline 3D e das
configurações. Ela sugere; o dono aceita, edita ou descarta. Nada é gravado direto.
"""

from pydantic import BaseModel, Field

VERSION = "enrich_product/v1"


class FaqItem(BaseModel):
    question: str = Field(max_length=200)
    answer: str = Field(max_length=600)


class ProductSuggestion(BaseModel):
    title: str = Field(max_length=120, description="título público, sem marca de terceiros")
    title_short: str = Field(max_length=60, description="versão curta para canais com limite")
    category: str = Field(max_length=60, description="slug minúsculo com hífen, ex.: nossa-senhora")
    subcategory: str | None = Field(default=None, max_length=60)
    description: str = Field(max_length=2500)
    bullets: list[str] = Field(
        max_length=6, description="material, cuidados, uso; sem números inventados"
    )
    faq: list[FaqItem] = Field(max_length=5)
    tags: list[str] = Field(max_length=15)
    occasions: list[str] = Field(max_length=6)
    color_ideas: list[str] = Field(max_length=6, description="nomes de cores por parte da peça")
    seo_title: str = Field(max_length=70)
    seo_description: str = Field(max_length=160)


SYSTEM = """Você redige anúncios de produtos impressos em 3D para a loja "{loja}".
Voz da marca: {voz_marca}
Voz deste nicho ({nicho}): {voz_nicho}

Regras inegociáveis:
- Português do Brasil, linguagem respeitosa.
- NUNCA invente números: medidas, peso, gramas, tempo de impressão, prazos ou preço. Se o
  pedido trouxer uma medida (ex.: "15cm"), pode repeti-la; nunca crie outras.
- Nunca use marcas, personagens, times ou logos de terceiros. Marca de carro/celular só no
  formato "compatível com <marca> <modelo>".
- Não chame nada de brinquedo. Não prometa resultado. Não sugira uso com chama (velas só LED).
- Recipientes para comida: "para alimentos embalados".
- Inclua um bullet dizendo que é feito em impressão 3D e que linhas de camada podem aparecer.
- Categoria e subcategoria em slug minúsculo com hífen."""

USER = """Produto descrito pelo dono: "{dica}"
Nicho: {nicho}{categoria}
Gere a sugestão completa."""


def build(
    *, loja: str, voz_marca: str, nicho: str, voz_nicho: str, dica: str, categoria: str | None
) -> tuple[str, str]:
    system = SYSTEM.format(
        loja=loja,
        voz_marca=voz_marca or "acolhedora e clara",
        nicho=nicho,
        voz_nicho=voz_nicho or "clara e objetiva",
    )
    user = USER.format(
        dica=dica.strip(),
        nicho=nicho,
        categoria=f"\nCategoria atual: {categoria}" if categoria else "",
    )
    return system, user
