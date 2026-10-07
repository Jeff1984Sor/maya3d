from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.db.session import get_session
from print3d_api.models import Product, Variant
from print3d_api.schemas.catalog import (
    DesignOut,
    ProductCreate,
    ProductDetail,
    ProductPatch,
    ProductSummary,
    VariantIn,
    VariantOut,
    VariantPatch,
    VariantQuoteOut,
)
from print3d_api.services import catalog
from print3d_api.services.guardian import UnknownNicheError
from print3d_core.guardian import material_available

router = APIRouter(prefix="/products", tags=["admin: produtos"])
Session = Annotated[AsyncSession, Depends(get_session)]


def _errors(exc: Exception) -> HTTPException:
    if isinstance(exc, catalog.NotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


async def _detail(session: AsyncSession, product_id: int) -> ProductDetail:
    product, design = await catalog.get_product(session, product_id)
    variants = (
        await session.scalars(
            select(Variant).where(Variant.product_id == product.id).order_by(Variant.id)
        )
    ).all()
    kinds = await catalog.printable_kinds(session)
    return ProductDetail.model_validate(
        {
            **ProductSummary.model_validate(product).model_dump(),
            "variant_count": len(variants),
            "available": material_available(product.min_material, kinds),
            "design": DesignOut.model_validate(design),
            "variants": [VariantOut.model_validate(v) for v in variants],
            "disclaimers": product.disclaimers,
            "attribution_required": product.attribution_required,
        }
    )


@router.get("", response_model=list[ProductSummary])
async def list_products(
    session: Session,
    niche: str | None = None,
    guardian: Annotated[str | None, Query(alias="guardiao")] = None,
) -> list[ProductSummary]:
    stmt = select(Product).order_by(Product.updated_at.desc())
    if niche:
        stmt = stmt.where(Product.niche == niche)
    if guardian:
        stmt = stmt.where(Product.guardian_status == guardian)
    products = (await session.scalars(stmt)).all()
    counts = await catalog.variant_counts(session, [p.id for p in products])
    kinds = await catalog.printable_kinds(session)
    return [
        ProductSummary.model_validate(p).model_copy(
            update={
                "variant_count": counts.get(p.id, 0),
                "available": material_available(p.min_material, kinds),
            }
        )
        for p in products
    ]


@router.post("", response_model=ProductDetail, status_code=status.HTTP_201_CREATED)
async def create_product(payload: ProductCreate, session: Session) -> ProductDetail:
    """Cria design + produto e roda o Guardião na hora (bloqueado fica em rascunho)."""
    try:
        product = await catalog.create_product(session, payload)
    except UnknownNicheError as exc:
        raise _errors(exc) from exc
    return await _detail(session, product.id)


@router.get("/{product_id}", response_model=ProductDetail)
async def get_product(product_id: int, session: Session) -> ProductDetail:
    try:
        return await _detail(session, product_id)
    except catalog.NotFoundError as exc:
        raise _errors(exc) from exc


@router.patch("/{product_id}", response_model=ProductDetail)
async def patch_product(product_id: int, payload: ProductPatch, session: Session) -> ProductDetail:
    try:
        await catalog.update_product(session, product_id, payload)
    except (catalog.NotFoundError, catalog.CatalogRuleError, UnknownNicheError) as exc:
        await session.rollback()
        raise _errors(exc) from exc
    return await _detail(session, product_id)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: int, session: Session) -> Response:
    try:
        product, _ = await catalog.get_product(session, product_id)
    except catalog.NotFoundError as exc:
        raise _errors(exc) from exc
    for variant in (
        await session.scalars(select(Variant).where(Variant.product_id == product_id))
    ).all():
        await session.delete(variant)
    await session.delete(product)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{product_id}/variants", response_model=VariantOut, status_code=201)
async def add_variant(product_id: int, payload: VariantIn, session: Session) -> Variant:
    try:
        return await catalog.add_variant(session, product_id, payload)
    except catalog.NotFoundError as exc:
        raise _errors(exc) from exc


@router.patch("/{product_id}/variants/{variant_id}", response_model=VariantOut)
async def patch_variant(
    product_id: int, variant_id: int, payload: VariantPatch, session: Session
) -> Variant:
    try:
        return await catalog.update_variant(session, product_id, variant_id, payload)
    except catalog.NotFoundError as exc:
        raise _errors(exc) from exc


@router.delete("/{product_id}/variants/{variant_id}", status_code=204)
async def delete_variant(product_id: int, variant_id: int, session: Session) -> Response:
    try:
        await catalog.delete_variant(session, product_id, variant_id)
    except catalog.NotFoundError as exc:
        raise _errors(exc) from exc
    return Response(status_code=204)


@router.get("/{product_id}/variants/{variant_id}/quote", response_model=VariantQuoteOut)
async def quote_variant(
    product_id: int,
    variant_id: int,
    session: Session,
    channels: Annotated[list[str] | None, Query()] = None,
) -> VariantQuoteOut:
    try:
        return await catalog.quote_variant(session, product_id, variant_id, channels)
    except catalog.NotFoundError as exc:
        raise _errors(exc) from exc
