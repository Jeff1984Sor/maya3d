"""O que imprimir em cada item do pedido: foto da peça e arquivos 3D (STL/3MF) para baixar.

- Peça da Biblioteca: todos os arquivos do modelo (peças em várias cores vêm separadas).
- Kit: os arquivos de cada peça do kit, com a quantidade.
- Paramétrico (nome personalizado): não há arquivo pronto; o painel aponta o gerador.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.models import Design, LibraryModel, OrderItem, Product, ProductImage, Variant

PREFIX = "library"  # o mesmo de services.library (importar de lá daria ciclo com store/orders)
MESH = (".stl", ".3mf", ".obj")


async def _cover(session: AsyncSession, product_id: int) -> str | None:
    image = await session.scalar(
        select(ProductImage)
        .where(ProductImage.product_id == product_id)
        .order_by(ProductImage.position, ProductImage.id)
        .limit(1)
    )
    return image.thumb_key if image else None


async def _files(session: AsyncSession, product: Product) -> list[dict[str, str]]:
    models = (
        await session.scalars(select(LibraryModel).where(LibraryModel.product_id == product.id))
    ).all()
    files = [
        {"name": f["name"], "key": f"{PREFIX}/{m.collection_slug}/modelos/{m.key}/{f['name']}"}
        for m in models
        for f in m.files
        if str(f.get("name", "")).lower().endswith(MESH)
    ]
    if files:
        return files
    design = await session.get(Design, product.design_id)
    key = design.source_file_url if design else None
    if key and not key.startswith(("http://", "https://")):
        return [{"name": key.rsplit("/", 1)[-1], "key": key}]
    return []


async def item_production(session: AsyncSession, item: OrderItem) -> dict[str, Any] | None:
    if item.variant_id is None:
        return None
    variant = await session.get(Variant, item.variant_id)
    product = await session.get(Product, variant.product_id) if variant else None
    if variant is None or product is None:
        return None
    design = await session.get(Design, product.design_id)
    parametric = str((design.params_schema or {}).get("model") or "") if design else ""
    parts: list[dict[str, Any]] = []
    for entry in (variant.params or {}).get("kit") or []:
        title, quantity = str(entry[0]), int(entry[1])
        part = await session.scalar(select(Product).where(Product.title == title).limit(1))
        parts.append(
            {
                "title": title,
                "quantity": quantity,
                "product_id": part.id if part else None,
                "files": await _files(session, part) if part else [],
            }
        )
    return {
        "product_id": product.id,
        "product_title": product.title,
        "size_label": variant.size_label,
        "image": await _cover(session, product.id),
        "parametric": parametric or None,
        "files": [] if parts or parametric else await _files(session, product),
        "kit": parts,
    }
