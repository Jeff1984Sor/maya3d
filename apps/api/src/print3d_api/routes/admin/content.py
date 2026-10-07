"""Painel → loja: marca, fotos de produto, página inicial e páginas institucionais."""

import re
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.db.session import get_session
from print3d_api.deps import get_storage
from print3d_api.models import BrandSettings, StorePage
from print3d_api.models.brand import SINGLETON_ID
from print3d_api.services import audit, content, media
from print3d_core.storage import LocalStorage

router = APIRouter(tags=["admin: loja e marca"])
Session = Annotated[AsyncSession, Depends(get_session)]
Storage = Annotated[LocalStorage, Depends(get_storage)]
TOKENS = ("bg", "surface", "ink", "muted", "primary", "secondary", "border")
HEX = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
SLUG = re.compile(r"^[a-z0-9-]{2,80}$")
MAX_IMAGE_BYTES = media.MAX_BYTES


async def _read(file: UploadFile) -> bytes:
    data = await file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "imagem acima de 20 MB")
    return data


def _http(exc: content.ContentError) -> HTTPException:
    code = status.HTTP_404_NOT_FOUND if exc.not_found else status.HTTP_422_UNPROCESSABLE_ENTITY
    return HTTPException(code, str(exc))


# --- Marca ----------------------------------------------------------------------------------
class BrandIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    tagline: str | None = Field(default=None, max_length=240)
    colors: dict[Literal["light", "dark"], dict[str, str]]
    contact_email: str | None = Field(default=None, max_length=255)
    contact_whatsapp: str | None = Field(default=None, max_length=32)
    social: dict[str, str] = {}
    cnpj: str | None = Field(default=None, max_length=18)
    legal_name: str | None = Field(default=None, max_length=255)
    voice: str | None = Field(default=None, max_length=2000)

    @field_validator("colors")
    @classmethod
    def _cores(cls, v: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
        for mode in ("light", "dark"):
            palette = v.get(mode, {})
            bad = [k for k, c in palette.items() if k not in TOKENS or not HEX.match(c)]
            if bad:
                raise ValueError(f"cor inválida em {mode}: {', '.join(bad)} (use #RRGGBB)")
        return v

    @field_validator("social")
    @classmethod
    def _redes(cls, v: dict[str, str]) -> dict[str, str]:
        for key, url in v.items():
            if url and not url.startswith("https://"):
                raise ValueError(f"{key}: use um link https://")
        return {k: u for k, u in v.items() if u}


class BrandAdmin(BrandIn):
    model_config = ConfigDict(from_attributes=True)
    logo_light_url: str | None
    logo_dark_url: str | None
    favicon_url: str | None


@router.get("/brand", response_model=BrandAdmin)
async def get_brand(session: Session) -> BrandSettings:
    row = await session.get(BrandSettings, SINGLETON_ID)
    if row is None:
        raise HTTPException(503, "marca não configurada (migrações)")
    return row


@router.put("/brand", response_model=BrandAdmin)
async def put_brand(payload: BrandIn, request: Request, session: Session) -> BrandSettings:
    row = await session.get(BrandSettings, SINGLETON_ID)
    if row is None:
        raise HTTPException(503, "marca não configurada (migrações)")
    data = payload.model_dump()
    data["colors"] = {
        mode: {**row.colors.get(mode, {}), **data["colors"].get(mode, {})}
        for mode in ("light", "dark")
    }
    for field, value in data.items():
        setattr(row, field, value)
    await audit.record(
        session, actor="admin", action="marca_alterada", payload={"nome": payload.name}
    )
    await session.commit()
    request.app.state.brand_service.invalidate()
    await session.refresh(row)
    return row


@router.post("/brand/logo/{kind}", response_model=BrandAdmin)
async def upload_logo(
    kind: Literal["light", "dark", "favicon"],
    file: UploadFile,
    request: Request,
    session: Session,
    storage: Storage,
) -> BrandSettings:
    row = await session.get(BrandSettings, SINGLETON_ID)
    if row is None:
        raise HTTPException(503, "marca não configurada (migrações)")
    try:
        saved = media.save_image(storage, await _read(file), folder="marca")
    except media.MediaError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    field = "favicon_url" if kind == "favicon" else f"logo_{kind}_url"
    # favicon usa a miniatura; logo usa a imagem inteira
    setattr(row, field, media.public_url(saved.thumb_key if kind == "favicon" else saved.key))
    await session.commit()
    request.app.state.brand_service.invalidate()
    await session.refresh(row)
    return row


# --- Fotos do produto ----------------------------------------------------------------------
class ImageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    key: str
    thumb_key: str
    alt: str | None
    position: int


@router.get("/products/{product_id}/images", response_model=list[ImageOut])
async def list_images(product_id: int, session: Session) -> list[Any]:
    return await content.images_of(session, product_id)


@router.post("/products/{product_id}/images", response_model=ImageOut, status_code=201)
async def upload_image(
    product_id: int, file: UploadFile, session: Session, storage: Storage
) -> Any:
    try:
        return await content.add_image(session, storage, product_id, await _read(file))
    except content.ContentError as exc:
        raise _http(exc) from exc


@router.delete("/products/{product_id}/images/{image_id}", status_code=204)
async def delete_image(product_id: int, image_id: int, session: Session, storage: Storage) -> None:
    try:
        await content.delete_image(session, storage, product_id, image_id)
    except content.ContentError as exc:
        raise _http(exc) from exc


@router.post("/products/{product_id}/images/{image_id}/cover", status_code=204)
async def make_cover(product_id: int, image_id: int, session: Session) -> None:
    try:
        await content.make_cover(session, product_id, image_id)
    except content.ContentError as exc:
        raise _http(exc) from exc


# --- Página inicial -------------------------------------------------------------------------
@router.get("/store-layout")
async def get_layout(session: Session) -> dict[str, Any]:
    row = await content.layout(session)
    await session.commit()
    return {"announcement": row.announcement, "hero": row.hero, "sections": row.sections}


@router.put("/store-layout")
async def put_layout(payload: content.LayoutIn, session: Session) -> dict[str, Any]:
    row = await content.save_layout(session, payload)
    return {"announcement": row.announcement, "hero": row.hero, "sections": row.sections}


@router.post("/store-layout/hero-image")
async def hero_image(file: UploadFile, session: Session, storage: Storage) -> dict[str, Any]:
    try:
        saved = media.save_image(storage, await _read(file), folder="home")
    except media.MediaError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    row = await content.layout(session)
    row.hero = {**(row.hero or {}), "image_key": saved.key}
    await session.commit()
    return {"image_key": saved.key}


# --- Páginas --------------------------------------------------------------------------------
class PageOut(content.PageIn):
    model_config = ConfigDict(from_attributes=True)
    slug: str


@router.get("/pages", response_model=list[PageOut])
async def list_pages(session: Session) -> list[StorePage]:
    return await content.pages(session, only_published=False)


@router.get("/pages/{slug}", response_model=PageOut)
async def get_page(slug: str, session: Session) -> StorePage:
    page = await session.get(StorePage, slug)
    if page is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "página não existe")
    return page


@router.put("/pages/{slug}", response_model=PageOut)
async def put_page(slug: str, payload: content.PageIn, session: Session) -> StorePage:
    if not SLUG.match(slug):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "endereço: letras minúsculas, números e hífen"
        )
    return await content.save_page(session, slug, payload)


@router.delete("/pages/{slug}", status_code=204)
async def delete_page(slug: str, session: Session) -> None:
    page = await session.get(StorePage, slug)
    if page is not None:
        await session.delete(page)
        await audit.record(session, actor="admin", action="pagina_removida", payload={"slug": slug})
        await session.commit()
