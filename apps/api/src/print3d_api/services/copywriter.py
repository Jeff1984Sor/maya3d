"""✍️ Redator por canal: textos de loja, Mercado Livre, Shopee e Instagram a partir do produto.

A IA recebe só fatos do banco. Depois, conferências que não dependem do modelo: Guardião,
números que não estão nos fatos, contato externo em marketplace e limite de título. O dono
revisa, edita e aprova; "aplicar na loja" grava título e descrição no produto (e o Guardião
verifica de novo).
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_ai import AITask
from print3d_ai.guards import contact_info, unknown_numbers
from print3d_ai.prompts import channel_copy
from print3d_api.models import BrandSettings, ChannelCopy, Material, Niche, Product, Variant
from print3d_api.models.brand import SINGLETON_ID
from print3d_api.schemas.catalog import ProductPatch
from print3d_api.schemas.governance import GuardianCheckIn
from print3d_api.services import audit, catalog, guardian
from print3d_api.services.ai import ProviderFactory, effective_settings

CHANNELS = tuple(channel_copy.PROFILES)


class CopyError(Exception):
    def __init__(self, message: str, *, not_found: bool = False) -> None:
        super().__init__(message)
        self.not_found = not_found


def _fit_title(title: str, limit: int) -> str:
    title = " ".join(title.split())
    if len(title) <= limit:
        return title
    cut = title[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:-") or title[:limit]


async def facts_for(session: AsyncSession, product: Product) -> str:
    """Fonte da verdade que a IA recebe (e contra a qual os números são conferidos)."""
    niche = await session.scalar(select(Niche).where(Niche.slug == product.niche))
    variants = (
        await session.scalars(select(Variant).where(Variant.product_id == product.id))
    ).all()
    material_ids = {
        int(str(m))
        for v in variants
        for m in [*(v.grams_by_material or {}), *v.color_by_part.values()]
        if str(m).isdigit()
    }
    materials = (
        (await session.scalars(select(Material).where(Material.id.in_(material_ids)))).all()
        if material_ids
        else []
    )
    lines = [
        f"Título atual: {product.title}",
        f"Nicho: {niche.name if niche else product.niche}",
        f"Categoria: {product.category}"
        + (f" / {product.subcategory}" if product.subcategory else ""),
        f"Descrição atual: {product.description}" if product.description else "",
        f"Tags: {', '.join(product.tags)}" if product.tags else "",
        f"Ocasiões: {', '.join(product.occasions)}" if product.occasions else "",
        "Personalizável: sim (nome, data ou frase)" if product.customizable else "",
        f"Material mínimo: {product.min_material}" if product.min_material else "",
        "Materiais/cores: " + ", ".join(f"{m.kind} {m.color_name}" for m in materials)
        if materials
        else "",
        *(
            "Variação: "
            + ", ".join(
                x
                for x in (
                    v.size_label,
                    "pintada à mão" if v.finish == "pintada" else "",
                    " x ".join(f"{d:g}" for d in v.dims_mm) + " mm" if v.dims_mm else "",
                )
                if x
            )
            for v in variants
        ),
        "Avisos obrigatórios: " + " ".join(product.disclaimers) if product.disclaimers else "",
    ]
    return "\n".join(line for line in lines if line and not line.endswith(": "))


async def _check(session: AsyncSession, product: Product, row: ChannelCopy, facts: str) -> None:
    profile = channel_copy.PROFILES[row.channel]
    text = "\n".join([row.title, row.description, *row.bullets])
    issues: list[str] = []
    if len(row.title) > profile.title_max:
        issues.append(f"título acima de {profile.title_max} caracteres")
    numbers = unknown_numbers(text, facts)
    if numbers:
        issues.append("números que não estão nos dados do produto: " + ", ".join(numbers))
    if profile.marketplace:
        contacts = contact_info(text)
        if contacts:
            issues.append("contato/link externo proibido no marketplace: " + ", ".join(contacts))
    decision = await guardian.decide(
        session,
        GuardianCheckIn(
            niche=product.niche,
            title=row.title,
            description="\n".join([row.description, *row.bullets]),
            tags=[*row.keywords, *row.hashtags],
            occasions=list(product.occasions),
            category=product.category,
            origin="parametrico",
            channel=row.channel,
        ),
    )
    row.guardian_status = decision.verdict
    issues.extend(f"Guardião: {v.message}" for v in decision.violations)
    row.issues = issues


async def generate(
    session: AsyncSession, factory: ProviderFactory, product_id: int, channels: Sequence[str]
) -> list[ChannelCopy]:
    product = await session.get(Product, product_id)
    if product is None:
        raise CopyError(f"produto {product_id} não existe", not_found=True)
    wanted = [c for c in CHANNELS if c in channels]
    if not wanted:
        raise CopyError(f"escolha ao menos um canal: {', '.join(CHANNELS)}")
    settings = await effective_settings(session)
    model = settings.model_for(AITask.DEFAULT)
    provider = factory(settings)
    brand = await session.get(BrandSettings, SINGLETON_ID)
    niche = await session.scalar(select(Niche).where(Niche.slug == product.niche))
    facts = await facts_for(session, product)
    system, prompt = channel_copy.build(
        loja=brand.name if brand else "a loja",
        voz_marca=(brand.voice or "") if brand else "",
        nicho=niche.name if niche else product.niche,
        voz_nicho=(niche.voice or "") if niche else "",
        facts=facts,
        channels=wanted,
    )
    result = await provider.complete_json(
        system=system, prompt=prompt, schema=channel_copy.CopySet, model=model
    )
    existing = {
        c.channel: c
        for c in (
            await session.scalars(select(ChannelCopy).where(ChannelCopy.product_id == product.id))
        ).all()
    }
    out: list[ChannelCopy] = []
    for item in result.items:
        if item.channel not in wanted or any(r.channel == item.channel for r in out):
            continue
        row = existing.get(item.channel) or ChannelCopy(product_id=product.id, channel=item.channel)
        if row.id is None:
            session.add(row)
        row.title = _fit_title(item.title, channel_copy.PROFILES[item.channel].title_max)
        row.description = item.description.strip()
        row.bullets = [b.strip() for b in item.bullets if b.strip()]
        row.keywords = [k.strip() for k in item.keywords if k.strip()]
        row.hashtags = (
            [h.strip().lstrip("#") for h in item.hashtags if h.strip()]
            if item.channel == "instagram"
            else []
        )
        row.status = "rascunho"
        row.model = model
        row.prompt_version = channel_copy.VERSION
        await _check(session, product, row, facts)
        out.append(row)
    await audit.record(
        session,
        actor="ia",
        action="textos_por_canal",
        entity_type="product",
        entity_id=product.id,
        payload={"canais": [r.channel for r in out], "modelo": model},
    )
    await session.commit()
    return out


async def list_for(session: AsyncSession, product_id: int) -> list[ChannelCopy]:
    rows = (
        await session.scalars(select(ChannelCopy).where(ChannelCopy.product_id == product_id))
    ).all()
    return sorted(rows, key=lambda r: CHANNELS.index(r.channel) if r.channel in CHANNELS else 99)


async def _get(session: AsyncSession, copy_id: int) -> tuple[ChannelCopy, Product]:
    row = await session.get(ChannelCopy, copy_id)
    product = await session.get(Product, row.product_id) if row else None
    if row is None or product is None:
        raise CopyError("texto não existe", not_found=True)
    return row, product


async def edit(session: AsyncSession, copy_id: int, data: dict[str, Any]) -> ChannelCopy:
    row, product = await _get(session, copy_id)
    for field in ("title", "description", "bullets", "keywords", "hashtags"):
        if data.get(field) is not None:
            setattr(row, field, data[field])
    row.status = "rascunho"  # editou: aprova de novo
    await _check(session, product, row, await facts_for(session, product))
    await session.commit()
    return row


async def set_status(session: AsyncSession, copy_id: int, new_status: str) -> ChannelCopy:
    row, _ = await _get(session, copy_id)
    if new_status == "aprovado" and row.guardian_status == "bloqueado":
        raise CopyError("o Guardião bloqueou este texto; edite antes de aprovar")
    row.status = new_status
    await audit.record(
        session,
        actor="admin",
        action=f"texto_{new_status}",
        entity_type="channel_copy",
        entity_id=row.id,
        payload={"canal": row.channel, "produto": row.product_id},
    )
    await session.commit()
    return row


async def apply_to_product(session: AsyncSession, copy_id: int) -> Product:
    """Texto da loja aprovado → título e descrição do produto (Guardião roda de novo)."""
    row, product = await _get(session, copy_id)
    if row.channel != "site":
        raise CopyError("só o texto da loja vai para o produto; os outros vão para os canais")
    if row.status != "aprovado":
        raise CopyError("aprove o texto antes de aplicar")
    bullets = "\n".join(f"• {b}" for b in row.bullets)
    description = f"{row.description}\n\n{bullets}".strip() if bullets else row.description
    try:
        return await catalog.update_product(
            session, product.id, ProductPatch(title=row.title, description=description)
        )
    except catalog.NotFoundError as exc:
        raise CopyError(str(exc), not_found=True) from exc
