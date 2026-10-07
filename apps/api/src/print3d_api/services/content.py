"""Conteúdo da loja: fotos de produto, página inicial e páginas institucionais."""

import asyncio
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.models import Product, ProductImage, StoreLayout, StorePage
from print3d_api.models.content import STORE_LAYOUT_ID
from print3d_api.schemas.store import StoreProductCard
from print3d_api.services import audit, media, store
from print3d_core.storage import LocalStorage

SECTION_KINDS = ("newest", "niche", "category", "tag", "manual")
MAX_IMAGES = 12


class ContentError(Exception):
    def __init__(self, message: str, *, not_found: bool = False) -> None:
        super().__init__(message)
        self.not_found = not_found


# --- Fotos de produto -----------------------------------------------------------------------
async def images_of(session: AsyncSession, product_id: int) -> list[ProductImage]:
    return list(
        (
            await session.scalars(
                select(ProductImage)
                .where(ProductImage.product_id == product_id)
                .order_by(ProductImage.position, ProductImage.id)
            )
        ).all()
    )


async def add_image(
    session: AsyncSession,
    storage: LocalStorage,
    product_id: int,
    data: bytes,
    alt: str | None = None,
    *,
    commit: bool = True,
) -> ProductImage:
    if await session.get(Product, product_id) is None:
        raise ContentError("produto não existe", not_found=True)
    current = await images_of(session, product_id)
    if len(current) >= MAX_IMAGES:
        raise ContentError(f"no máximo {MAX_IMAGES} fotos por produto")
    try:
        saved = media.save_image(storage, data, folder=f"produtos/{product_id}")
    except media.MediaError as exc:
        raise ContentError(str(exc)) from exc
    position = (max(i.position for i in current) + 1) if current else 0
    img = ProductImage(
        product_id=product_id,
        key=saved.key,
        thumb_key=saved.thumb_key,
        alt=(alt or None) and alt[:200],
        position=position,
    )
    session.add(img)
    if commit:
        await session.commit()
    return img


async def add_image_from_file(
    session: AsyncSession, storage: LocalStorage, product_id: int, path: Path
) -> ProductImage | None:
    """Capa da Biblioteca → primeira foto do produto (se for imagem válida)."""
    try:
        data = await asyncio.to_thread(path.read_bytes)
        return await add_image(session, storage, product_id, data, commit=False)
    except (ContentError, OSError):
        return None


async def delete_image(
    session: AsyncSession, storage: LocalStorage, product_id: int, image_id: int
) -> None:
    img = await session.get(ProductImage, image_id)
    if img is None or img.product_id != product_id:
        raise ContentError("foto não existe", not_found=True)
    media.delete(storage, img.key, img.thumb_key)
    await session.delete(img)
    await session.commit()


async def make_cover(session: AsyncSession, product_id: int, image_id: int) -> None:
    images = await images_of(session, product_id)
    if not any(i.id == image_id for i in images):
        raise ContentError("foto não existe", not_found=True)
    ordered = sorted(images, key=lambda i: (i.id != image_id, i.position, i.id))
    for pos, img in enumerate(ordered):
        img.position = pos
    await session.commit()


# --- Página inicial -------------------------------------------------------------------------
class Hero(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    subtitle: str | None = Field(default=None, max_length=240)
    image_key: str | None = Field(default=None, max_length=200)
    cta_label: str | None = Field(default=None, max_length=40)
    cta_href: str | None = Field(default=None, max_length=200)

    @field_validator("cta_href")
    @classmethod
    def _so_interno(cls, v: str | None) -> str | None:
        # botão só leva para dentro da loja (nada de link para fora / javascript:)
        if v and not (v.startswith("/") and not v.startswith("//")):
            raise ValueError("use um caminho da loja, ex.: /c/religioso ou /busca?q=terco")
        return v or None

    @field_validator("image_key")
    @classmethod
    def _so_midia(cls, v: str | None) -> str | None:
        if v and not v.startswith(f"{media.PREFIX}/"):
            raise ValueError("imagem inválida")
        return v or None


class Section(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    kind: str = "newest"
    value: str = Field(default="", max_length=600)
    limit: int = Field(default=8, ge=1, le=24)

    @field_validator("kind")
    @classmethod
    def _tipo(cls, v: str) -> str:
        if v not in SECTION_KINDS:
            raise ValueError(f"tipo de vitrine: {', '.join(SECTION_KINDS)}")
        return v


class LayoutIn(BaseModel):
    announcement: str | None = Field(default=None, max_length=200)
    hero: Hero = Hero()
    sections: list[Section] = Field(default_factory=list, max_length=8)


class HomeSection(BaseModel):
    title: str
    href: str | None
    products: list[StoreProductCard]


class HomeOut(BaseModel):
    announcement: str | None
    hero: dict[str, Any]
    sections: list[HomeSection]


async def layout(session: AsyncSession) -> StoreLayout:
    row = await session.get(StoreLayout, STORE_LAYOUT_ID)
    if row is None:
        row = StoreLayout(id=STORE_LAYOUT_ID, hero={}, sections=[])
        session.add(row)
        await session.flush()
    return row


async def save_layout(session: AsyncSession, data: LayoutIn) -> StoreLayout:
    row = await layout(session)
    row.announcement = (data.announcement or "").strip() or None
    row.hero = data.hero.model_dump()
    row.sections = [s.model_dump() for s in data.sections]
    await audit.record(session, actor="admin", action="loja_inicio_alterado")
    await session.commit()
    return row


def _section_href(kind: str, value: str) -> str | None:
    if kind == "niche" and value:
        return f"/c/{value}"
    if kind in ("category", "tag") and value:
        return f"/busca?q={value}"
    return "/busca" if kind == "newest" else None


async def home(session: AsyncSession) -> HomeOut:
    row = await layout(session)
    hero = dict(row.hero or {})
    hero["image"] = media.public_url(hero.pop("image_key", None))
    sections = []
    for raw in row.sections or []:
        sec = Section.model_validate(raw)
        cards = await store.section_cards(session, sec.kind, sec.value, sec.limit)
        if cards:
            sections.append(
                HomeSection(
                    title=sec.title, href=_section_href(sec.kind, sec.value), products=cards
                )
            )
    return HomeOut(announcement=row.announcement, hero=hero, sections=sections)


# --- Páginas --------------------------------------------------------------------------------
class PageIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(default="", max_length=30_000)
    published: bool = False
    in_footer: bool = True
    position: int = Field(default=0, ge=0, le=99)


async def pages(session: AsyncSession, *, only_published: bool) -> list[StorePage]:
    stmt = select(StorePage).order_by(StorePage.position, StorePage.title)
    if only_published:
        stmt = stmt.where(StorePage.published.is_(True))
    return list((await session.scalars(stmt)).all())


async def save_page(session: AsyncSession, slug: str, data: PageIn) -> StorePage:
    page = await session.get(StorePage, slug)
    if page is None:
        page = StorePage(slug=slug)
        session.add(page)
    for field, value in data.model_dump().items():
        setattr(page, field, value)
    await audit.record(
        session,
        actor="admin",
        action="pagina_salva",
        payload={"slug": slug, "publicada": data.published},
    )
    await session.commit()
    return page
