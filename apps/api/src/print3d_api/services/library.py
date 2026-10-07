"""Biblioteca de modelos: coleções, envio de arquivos, resultado do worker e criação de
produtos a partir dos modelos.

O worker escreve files/library/<slug>/colecao.json; `sync` lê e grava no banco (somando
modelos novos, sem apagar os anteriores). A licença da coleção vai para o Design de cada
produto criado: sem licença, o Guardião bloqueia; ao preencher, todos são verificados de novo.
"""

import json
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.models import Design, LibraryCollection, LibraryModel, Printer, Product
from print3d_api.schemas.catalog import DesignIn, ProductCreate
from print3d_api.services import audit, catalog, content
from print3d_core.storage import LocalStorage

PREFIX = "library"
ALLOWED = {".zip", ".stl", ".3mf", ".obj", ".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_BED = (256.0, 256.0, 256.0)


class LibraryError(Exception):
    def __init__(self, message: str, *, not_found: bool = False) -> None:
        super().__init__(message)
        self.not_found = not_found


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:70] or "colecao"


def safe_upload_name(name: str) -> str:
    base = Path(name).name  # nunca aceita caminho vindo do navegador
    ext = Path(base).suffix.lower()
    if ext not in ALLOWED:
        raise LibraryError(f"tipo não aceito: {ext or base} (ZIP, STL, 3MF, OBJ ou imagem)")
    stem = slugify(Path(base).stem) or "arquivo"
    return f"{stem}{ext}"


async def get_collection(session: AsyncSession, slug: str) -> LibraryCollection:
    col = await session.get(LibraryCollection, slug)
    if col is None:
        raise LibraryError("coleção não existe", not_found=True)
    return col


async def create_collection(session: AsyncSession, data: dict[str, Any]) -> LibraryCollection:
    base = slugify(data["title"])
    slug, n = base, 2
    while await session.get(LibraryCollection, slug) is not None:
        slug, n = f"{base}-{n}", n + 1
    col = LibraryCollection(slug=slug, status="vazio", **data)
    session.add(col)
    await audit.record(
        session, actor="admin", action="biblioteca_colecao_criada", payload={"slug": slug}
    )
    await session.commit()
    return col


def inbox_dir(storage: LocalStorage, slug: str) -> Path:
    return storage.local_path(f"{PREFIX}/{slug}/_envios/x").parent


async def bed_mm(session: AsyncSession) -> list[float]:
    """Maior mesa entre as impressoras ativas (sem impressora: 256 mm, padrão de mercado)."""
    printers = (await session.scalars(select(Printer))).all()
    active = [p for p in printers if p.status == "ativa"] or list(printers)
    if not active:
        return list(DEFAULT_BED)
    best = max(active, key=lambda p: p.bed_x_mm * p.bed_y_mm * p.bed_z_mm)
    return [float(best.bed_x_mm), float(best.bed_y_mm), float(best.bed_z_mm)]


async def sync(session: AsyncSession, storage: LocalStorage, col: LibraryCollection) -> None:
    """Lê o colecao.json do worker e grava os modelos novos."""
    path = storage.local_path(f"{PREFIX}/{col.slug}/colecao.json")
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return
    status = data.get("status")
    finished = data.get("finished_at")
    finished_at = datetime.fromisoformat(finished) if finished else None
    if status == "processando":
        col.status = "processando"
    elif status == "erro":
        col.status, col.error = "erro", data.get("error")
    elif (
        status == "pronto"
        and finished_at
        and (col.processed_at is None or finished_at > col.processed_at)
    ):
        existing = {
            m.key: m
            for m in (
                await session.scalars(
                    select(LibraryModel).where(LibraryModel.collection_slug == col.slug)
                )
            ).all()
        }
        for item in data.get("models", []):
            row = existing.get(item["key"])
            if row is None:
                row = LibraryModel(collection_slug=col.slug, key=item["key"], status="novo")
                session.add(row)
            row.title = item["title"][:200]
            row.files = item.get("files", [])
            row.cover = item.get("cover")
            row.bbox_mm = item.get("bbox_mm")
            row.fits = item.get("fits")
            row.issues = item.get("issues", [])
        warnings = data.get("warnings") or []
        col.status, col.error = "pronto", ("; ".join(warnings)[:2000] or None)
        col.processed_at = finished_at
    await session.commit()


async def list_collections(session: AsyncSession, storage: LocalStorage) -> list[dict[str, Any]]:
    cols = (
        await session.scalars(select(LibraryCollection).order_by(LibraryCollection.created_at))
    ).all()
    out = []
    for col in cols:
        if col.status == "processando":
            await sync(session, storage, col)
        models = (
            await session.scalars(
                select(LibraryModel).where(LibraryModel.collection_slug == col.slug)
            )
        ).all()
        inbox = inbox_dir(storage, col.slug)
        out.append(
            {
                "slug": col.slug,
                "title": col.title,
                "description": col.description,
                "category": col.category,
                "niche": col.niche,
                "license_text": col.license_text,
                "status": col.status,
                "error": col.error,
                "models": len(models),
                "products": sum(1 for m in models if m.status == "produto"),
                "pending_files": sorted(p.name for p in inbox.iterdir()) if inbox.is_dir() else [],
            }
        )
    return out


async def models_of(session: AsyncSession, slug: str) -> list[LibraryModel]:
    return list(
        (
            await session.scalars(
                select(LibraryModel)
                .where(LibraryModel.collection_slug == slug)
                .order_by(LibraryModel.status, LibraryModel.title)
            )
        ).all()
    )


def _main_file(model: LibraryModel) -> str | None:
    analyzed = [f for f in model.files if f.get("bbox_mm")]
    main = next((f for f in analyzed if not f["name"].endswith(".3mf")), None)
    main = main or (analyzed[0] if analyzed else (model.files[0] if model.files else None))
    return main["name"] if main else None


async def create_product(
    session: AsyncSession,
    model_id: int,
    title: str | None,
    storage: LocalStorage | None = None,
) -> tuple[LibraryModel, Product]:
    model = await session.get(LibraryModel, model_id)
    if model is None:
        raise LibraryError("modelo não existe", not_found=True)
    if model.product_id:
        raise LibraryError("este modelo já virou produto")
    col = await get_collection(session, model.collection_slug)
    main = _main_file(model)
    notes = "; ".join(model.issues) or None
    if model.fits is False:
        notes = "; ".join(x for x in ("não cabe na mesa: dividir em partes", notes) if x)
    product = await catalog.create_product(
        session,
        ProductCreate(
            niche=col.niche,
            category=col.category,
            title=(title or model.title)[:200],
            description=None,
            design=DesignIn(
                name=(title or model.title)[:160],
                origin="licenca_comercial",
                license=(col.license_text or "")[:80],
                source_file_url=(
                    f"{PREFIX}/{col.slug}/modelos/{model.key}/{main}" if main else None
                ),
                printability_notes=notes,
            ),
        ),
    )
    model.status, model.product_id = "produto", product.id
    if model.cover and storage is not None:
        cover = storage.local_path(f"{PREFIX}/{col.slug}/modelos/{model.key}/{model.cover}")
        await content.add_image_from_file(session, storage, product.id, cover)
    await session.commit()
    return model, product


async def set_license(session: AsyncSession, slug: str, license_text: str | None) -> int:
    """Grava a licença e verifica de novo todos os produtos da coleção. Devolve quantos."""
    col = await get_collection(session, slug)
    col.license_text = license_text
    ids = [m.product_id for m in await models_of(session, slug) if m.product_id is not None]
    count = 0
    for pid in ids:
        product = await session.get(Product, pid)
        design = await session.get(Design, product.design_id) if product else None
        if product and design:
            design.license = (license_text or "")[:80]
            await catalog.apply_guardian(session, product, design)
            count += 1
    await audit.record(
        session,
        actor="admin",
        action="biblioteca_licenca",
        payload={"slug": slug, "produtos": count, "preenchida": bool(license_text)},
    )
    await session.commit()
    return count


def mark_processing(col: LibraryCollection) -> None:
    col.status, col.error = "processando", None
    col.updated_at = datetime.now(UTC)
