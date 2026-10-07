"""conteúdo da loja: fotos de produto, página inicial e páginas institucionais

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-07

As páginas entram como RASCUNHO (não publicadas): o dono revisa no painel antes de publicar.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


PAGES = [
    (
        "como-comprar",
        "Como comprar",
        1,
        """## Como comprar

1. Escolha a peça e personalize (nome, cor, tamanho). Você vê a prévia em 3D antes.
2. No carrinho, informe o CEP para ver frete, entrega local ou retirada.
3. Pague com Pix. O pedido entra em produção assim que o pagamento é confirmado.
4. Acompanhe tudo pelo link do pedido.

**Pedidos grandes** (lembrancinhas, brindes de empresa): imprimimos uma amostra para você
aprovar antes de produzir o restante.""",
    ),
    (
        "trocas-e-devolucoes",
        "Trocas e devoluções",
        2,
        """## Trocas e devoluções

- **Arrependimento:** compras pela internet podem ser canceladas em até 7 dias do
  recebimento (Código de Defesa do Consumidor, art. 49), com a peça sem uso.
- **Peças personalizadas** (com nome, data ou frase) são feitas sob encomenda.
- **Defeito ou dano no transporte:** fale com a gente em até 7 dias com fotos da peça e da
  embalagem. Reimprimimos ou devolvemos o valor.

Peças impressas em 3D podem ter linhas de camada visíveis: é característica do processo.

*Rascunho: revise com a sua contadora/advogada antes de publicar.*""",
    ),
    (
        "privacidade",
        "Privacidade",
        3,
        """## Privacidade (LGPD)

Usamos seus dados (nome, contato, endereço) só para produzir, entregar e falar sobre o seu
pedido. Mensagens de novidades só com a sua autorização, e você pode sair quando quiser.

Fotos enviadas para virar peça são apagadas automaticamente depois de 30 dias.

Para ver, corrigir ou apagar seus dados, fale com a gente pelo contato da loja.

*Rascunho: revise antes de publicar.*""",
    ),
    (
        "sobre",
        "Sobre nós",
        4,
        """## Sobre nós

Somos uma loja de peças impressas em 3D feitas sob medida: presentes, lembrancinhas,
decoração e acessórios personalizados.

*Conte aqui a sua história.*""",
    ),
]


def upgrade() -> None:
    op.create_table(
        "product_images",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(200), nullable=False),
        sa.Column("thumb_key", sa.String(200), nullable=False),
        sa.Column("alt", sa.String(200)),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        *_ts(),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_product_images_product_id_products"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(op.f("ix_product_images_product_id"), "product_images", ["product_id"])
    layout = op.create_table(
        "store_layout",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("announcement", sa.String(200)),
        sa.Column("hero", JSONB, nullable=False, server_default="{}"),
        sa.Column("sections", JSONB, nullable=False, server_default="[]"),
        *_ts(),
        sa.CheckConstraint("id = 1", name=op.f("ck_store_layout_singleton")),
    )
    op.bulk_insert(
        layout,
        [
            {
                "id": 1,
                "announcement": None,
                "hero": {},
                "sections": [{"title": "Novidades", "kind": "newest", "value": "", "limit": 12}],
            }
        ],
    )
    pages = op.create_table(
        "store_pages",
        sa.Column("slug", sa.String(80), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("in_footer", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        *_ts(),
    )
    op.bulk_insert(
        pages,
        [
            {"slug": s, "title": t, "position": p, "body": b, "published": False, "in_footer": True}
            for s, t, p, b in PAGES
        ],
    )


def downgrade() -> None:
    op.drop_table("store_pages")
    op.drop_table("store_layout")
    op.drop_index(op.f("ix_product_images_product_id"), table_name="product_images")
    op.drop_table("product_images")
