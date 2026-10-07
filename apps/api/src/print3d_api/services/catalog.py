"""Regras do catálogo: Guardião automático a cada salvamento, disponibilidade por material
mínimo, SKU automático e preço por variante. Nenhuma aprovação manual (spec seção 2)."""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import asdict
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.models import Design, PackagingBox, Printer, Product, ProductImage, Variant
from print3d_api.schemas.catalog import (
    ProductCreate,
    ProductPatch,
    VariantIn,
    VariantPatch,
    VariantQuoteOut,
)
from print3d_api.schemas.governance import GuardianCheckIn
from print3d_api.schemas.pricing import QuoteRequest
from print3d_api.services import audit, guardian, pricing
from print3d_core.guardian import material_available


class CatalogRuleError(Exception):
    """Ação proibida pelas regras (ex.: ativar produto bloqueado)."""


class NotFoundError(Exception):
    pass


def slugify(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")[:200] or "produto"


async def _unique_slug(session: AsyncSession, title: str, exclude_id: int | None = None) -> str:
    base = slugify(title)
    slug, n = base, 1
    while True:
        stmt = select(Product.id).where(Product.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(Product.id != exclude_id)
        if await session.scalar(stmt) is None:
            return slug
        n += 1
        slug = f"{base}-{n}"


async def printable_kinds(session: AsyncSession) -> set[str]:
    """Materiais que alguma impressora ATIVA imprime."""
    printers = (await session.scalars(select(Printer).where(Printer.status == "ativa"))).all()
    return {k.upper() for p in printers for k in p.supported_materials}


async def apply_guardian(session: AsyncSession, product: Product, design: Design) -> None:
    decision = await guardian.decide(
        session,
        GuardianCheckIn(
            niche=product.niche,
            title=product.title,
            description=product.description or "",
            tags=list(product.tags),
            occasions=list(product.occasions),
            category=product.category,
            origin=design.origin,
            license=design.license,
            author=design.author,
            attribution_text=design.attribution_text,
        ),
    )
    product.guardian_status = decision.verdict
    product.guardian_reason = None if decision.approved else decision.reason
    blocked_photos = (
        await session.scalars(
            select(ProductImage.visual_notes).where(
                ProductImage.product_id == product.id, ProductImage.visual_status == "bloqueado"
            )
        )
    ).all()
    if blocked_photos:  # foto com personagem/marca de terceiro bloqueia mesmo com texto limpo
        seen = "; ".join(str(n.get("summary", "")) for n in blocked_photos if n)[:300]
        product.guardian_status = "bloqueado"
        product.guardian_reason = "; ".join(
            x
            for x in (product.guardian_reason, f"Guardião visual: {seen or 'foto bloqueada'}")
            if x
        )
    approved = product.guardian_status == "aprovado"
    product.disclaimers = list(decision.disclaimers)
    product.age_rating = decision.age_rating
    product.attribution_required = decision.attribution_required
    design.ip_status = decision.verdict
    design.ip_reason = product.guardian_reason
    design.attribution_required = decision.attribution_required
    if not approved and product.status == "ativo":
        product.status = "pausado"  # bloqueio novo derruba produto ativo
    await audit.record(
        session,
        actor="guardiao",
        action="produto_verificado",
        entity_type="product",
        entity_id=product.id,
        decision=product.guardian_status,
        reason=product.guardian_reason,
        payload={"titulo": product.title, "violacoes": [asdict(v) for v in decision.violations]},
    )


async def create_product(session: AsyncSession, data: ProductCreate) -> Product:
    design = Design(**data.design.model_dump(), attribution_required=False, ip_status="pendente")
    session.add(design)
    await session.flush()
    product = Product(
        **data.model_dump(exclude={"design"}),
        design_id=design.id,
        slug=await _unique_slug(session, data.title),
        status="rascunho",
    )
    session.add(product)
    await session.flush()
    await apply_guardian(session, product, design)
    await session.commit()
    await _reload(session, product, design)
    return product


async def _reload(session: AsyncSession, *objs: Product | Design) -> None:
    """Relê colunas geradas pelo banco (updated_at) dentro do contexto assíncrono; sem isso o
    SQLAlchemy tentaria carregar depois, fora do greenlet (MissingGreenlet)."""
    for obj in objs:
        await session.refresh(obj)


async def get_product(session: AsyncSession, product_id: int) -> tuple[Product, Design]:
    product = await session.get(Product, product_id)
    if product is None:
        raise NotFoundError(f"produto {product_id} não existe")
    design = await session.get(Design, product.design_id)
    assert design is not None
    return product, design


async def update_product(session: AsyncSession, product_id: int, patch: ProductPatch) -> Product:
    product, design = await get_product(session, product_id)
    data = patch.model_dump(exclude_unset=True, exclude={"design", "status"})
    for field, value in data.items():
        setattr(product, field, value)
    if "title" in data:
        product.slug = await _unique_slug(session, product.title, exclude_id=product.id)
    if patch.design is not None:
        for field, value in patch.design.model_dump().items():
            setattr(design, field, value)
    await apply_guardian(session, product, design)

    if patch.status is not None and patch.status != product.status:
        if patch.status == "ativo":
            if product.guardian_status != "aprovado":
                raise CatalogRuleError(f"Guardião bloqueou: {product.guardian_reason}")
            if not material_available(product.min_material, await printable_kinds(session)):
                raise CatalogRuleError(
                    "aguardando equipamento: nenhuma impressora ativa imprime "
                    f"{product.min_material}"
                )
        product.status = patch.status
        await audit.record(
            session,
            actor="admin",
            action="status_produto",
            entity_type="product",
            entity_id=product.id,
            decision=patch.status,
        )
    await session.commit()
    await _reload(session, product, design)
    return product


async def variant_counts(session: AsyncSession, ids: Sequence[int]) -> dict[int, int]:
    if not ids:
        return {}
    rows = await session.execute(
        select(Variant.product_id, func.count())
        .where(Variant.product_id.in_(ids))
        .group_by(Variant.product_id)
    )
    return {pid: int(n) for pid, n in rows.all()}


async def _next_sku(session: AsyncSession, product: Product) -> str:
    prefix = f"{slugify(product.niche)[:3].upper()}-{product.id:05d}-"
    count = await session.scalar(select(func.count()).where(Variant.product_id == product.id))
    n = int(count or 0) + 1
    while await session.scalar(select(Variant.id).where(Variant.sku == f"{prefix}{n:02d}")):
        n += 1
    return f"{prefix}{n:02d}"


def _slicing_source(grams: dict[str, float] | None, seconds: int | None) -> str:
    return "manual" if grams and seconds else "a_confirmar"


async def add_variant(session: AsyncSession, product_id: int, data: VariantIn) -> Variant:
    product, _ = await get_product(session, product_id)
    values = data.model_dump()
    values["sku"] = data.sku or await _next_sku(session, product)
    variant = Variant(
        **values,
        product_id=product.id,
        slicing_source=_slicing_source(data.grams_by_material, data.print_seconds),
    )
    session.add(variant)
    await session.commit()
    await session.refresh(variant)
    return variant


async def _get_variant(session: AsyncSession, product_id: int, variant_id: int) -> Variant:
    variant = await session.get(Variant, variant_id)
    if variant is None or variant.product_id != product_id:
        raise NotFoundError(f"variante {variant_id} não existe neste produto")
    return variant


async def update_variant(
    session: AsyncSession, product_id: int, variant_id: int, patch: VariantPatch
) -> Variant:
    variant = await _get_variant(session, product_id, variant_id)
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(variant, field, value)
    if variant.slicing_source != "fatiador":
        variant.slicing_source = _slicing_source(variant.grams_by_material, variant.print_seconds)
    await session.commit()
    await session.refresh(variant)
    return variant


async def delete_variant(session: AsyncSession, product_id: int, variant_id: int) -> None:
    await session.delete(await _get_variant(session, product_id, variant_id))
    await session.commit()


async def quote_variant(
    session: AsyncSession, product_id: int, variant_id: int, channels: list[str] | None
) -> VariantQuoteOut:
    product, _ = await get_product(session, product_id)
    variant = await _get_variant(session, product_id, variant_id)
    if not variant.grams_by_material or not variant.print_seconds:
        return VariantQuoteOut(
            ready=False, reason="a confirmar: faltam gramas e tempo (fatiador ou informe)"
        )

    printers = (await session.scalars(select(Printer).order_by(Printer.id))).all()
    printer = next((p for p in printers if p.status == "ativa"), None) or next(iter(printers), None)
    if printer is None:
        return VariantQuoteOut(ready=False, reason="cadastre uma impressora (pode ser planejada)")

    extras = Decimal(0)
    if variant.packaging_id:
        box = await session.get(PackagingBox, variant.packaging_id)
        extras = box.cost if box else Decimal(0)

    try:
        result = await pricing.quote(
            session,
            QuoteRequest(
                grams_by_material={
                    int(k): Decimal(str(v)) for k, v in variant.grams_by_material.items()
                },
                print_minutes=max(1, round(variant.print_seconds / 60)),
                printer_id=printer.id,
                post_minutes=variant.post_minutes,
                category=product.category,
                extra_costs=extras,
                channels=channels,
            ),
        )
    except pricing.QuoteInputError as exc:
        return VariantQuoteOut(ready=False, reason=str(exc))
    return VariantQuoteOut(
        ready=True,
        cost_total=result.cost.total,
        quotes=[q.model_dump(mode="json") for q in result.quotes],
        warnings=result.warnings,
    )
