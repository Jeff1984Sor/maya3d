"""👁️ Guardião visual: a IA olha cada foto do produto; o código decide (ok/alerta/bloqueado).

Foto bloqueada (personagem, marca, logo ou time com confiança alta) bloqueia o produto pelo
Guardião (ver catalog.apply_guardian). O dono pode liberar uma foto ("é meu" / "tenho
licença"): fica registrado na auditoria com o motivo.
"""

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from print3d_ai import AINotConfiguredError, AITask, ImageInput
from print3d_ai.prompts import guardian_visual
from print3d_api.models import Design, Product, ProductImage
from print3d_api.services import audit, catalog, content
from print3d_api.services.ai import ProviderFactory, effective_settings
from print3d_core.storage import LocalStorage

log = logging.getLogger("print3d.visual")


class VisualError(Exception):
    def __init__(self, message: str, *, not_found: bool = False) -> None:
        super().__init__(message)
        self.not_found = not_found


async def model_for(session: AsyncSession) -> str | None:
    """Modelo do Guardião (forte); sem ele, o visual fica desligado."""
    settings = await effective_settings(session)
    if settings.api_key is None or not settings.api_key.get_secret_value():
        return None
    try:
        return settings.model_for(AITask.GUARDIAN)
    except RuntimeError:
        return None


async def _recheck_product(session: AsyncSession, product_id: int) -> None:
    product = await session.get(Product, product_id)
    design = await session.get(Design, product.design_id) if product else None
    if product and design:
        await catalog.apply_guardian(session, product, design)


async def check_images(
    session: AsyncSession,
    factory: ProviderFactory,
    storage: LocalStorage,
    product_id: int,
    *,
    only_pending: bool = False,
) -> list[ProductImage]:
    product = await session.get(Product, product_id)
    if product is None:
        raise VisualError("produto não existe", not_found=True)
    model = await model_for(session)
    if model is None:
        raise AINotConfiguredError("Guardião visual desligado: escolha o modelo do Guardião (IA)")
    provider = factory(await effective_settings(session))
    images = await content.images_of(session, product_id)
    system, prompt = guardian_visual.build(titulo=product.title, nicho=product.niche)
    for img in images:
        if only_pending and img.visual_status != "pendente":
            continue
        if img.visual_status == "liberado":
            continue  # decisão do dono vale até a foto ser trocada
        try:
            data = await asyncio.to_thread(storage.local_path(img.key).read_bytes)
            verdict = await provider.complete_json(
                system=system,
                prompt=prompt,
                schema=guardian_visual.VisualVerdict,
                model=model,
                max_tokens=1500,
                images=[ImageInput(data, "image/webp")],
            )
        except Exception as exc:  # uma foto com erro não impede as outras
            log.warning("guardião visual falhou", extra={"imagem": img.id, "erro": str(exc)})
            img.visual_status = "erro"
            img.visual_notes = {"summary": f"não foi possível analisar: {type(exc).__name__}"}
            continue
        img.visual_status = guardian_visual.decide(verdict)
        img.visual_notes = {
            "summary": verdict.summary,
            "findings": [f.model_dump() for f in verdict.findings],
            "model": model,
            "prompt_version": guardian_visual.VERSION,
        }
        await audit.record(
            session,
            actor="guardiao_visual",
            action="foto_verificada",
            entity_type="product",
            entity_id=product_id,
            decision=img.visual_status,
            reason=verdict.summary[:300],
            payload={"imagem": img.id, "achados": img.visual_notes["findings"]},
        )
    await _recheck_product(session, product_id)
    await session.commit()
    return await content.images_of(session, product_id)


async def release(session: AsyncSession, product_id: int, image_id: int, reason: str) -> None:
    img = await session.get(ProductImage, image_id)
    if img is None or img.product_id != product_id:
        raise VisualError("foto não existe", not_found=True)
    previous = img.visual_status
    img.visual_status = "liberado"
    img.visual_notes = {**(img.visual_notes or {}), "released_reason": reason}
    await audit.record(
        session,
        actor="admin",
        action="foto_liberada_pelo_dono",
        entity_type="product",
        entity_id=product_id,
        decision="liberado",
        reason=reason,
        payload={"imagem": image_id, "antes": previous},
    )
    await _recheck_product(session, product_id)
    await session.commit()


async def check_in_background(
    factory_session: async_sessionmaker[AsyncSession],
    factory: ProviderFactory,
    storage: LocalStorage,
    product_id: int,
) -> None:
    """Depois do envio de fotos: analisa as pendentes se a IA estiver ligada (silencioso)."""
    try:
        async with factory_session() as session:
            if await model_for(session) is None:
                return
            await check_images(session, factory, storage, product_id, only_pending=True)
    except Exception:
        log.exception("guardião visual em segundo plano falhou")


def summary(images: list[ProductImage]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for img in images:
        counts[img.visual_status] = counts.get(img.visual_status, 0) + 1
    return counts
