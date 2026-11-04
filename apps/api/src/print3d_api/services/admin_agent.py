"""🤖 Assistente do painel: conversa com o dono e usa ferramentas do sistema.

Consulta (buscar imagens, produtos, pedidos) roda na hora. O que altera algo vira PROPOSTA
guardada no Redis por 1 hora e só roda quando o dono confirma (auditoria registra).
"""

import json
import secrets
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Literal

from arq.connections import ArqRedis
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_ai import AINotConfiguredError, AITask
from print3d_ai.image_search import ImageHit, ImageSearch, ImageSearchError
from print3d_ai.prompts import admin_agent
from print3d_api.models import BrandSettings, Order, Product
from print3d_api.models.brand import SINGLETON_ID
from print3d_api.schemas.catalog import ProductPatch, ProductStatus
from print3d_api.services import audit, catalog, integrations, photos
from print3d_api.services.ai import ProviderFactory, effective_settings
from print3d_api.services.guardian import UnknownNicheError
from print3d_core.storage import LocalStorage
from print3d_mesh.image3d import Image3DError

MAX_STEPS = 4
PROPOSAL_TTL = 3600
PROPOSAL_KEY = "agente:proposta:{}"
PhotoMode = Literal["litofania", "placa_multicor", "cortador", "chaveiro_silhueta", "objeto_3d"]
WIDTH_MODES = ("litofania", "placa_multicor")  # nesses, o tamanho é a largura


class AgentError(Exception):
    pass


# --- argumentos validados (a IA manda JSON; nada passa sem validar) ---------------------------
class SearchImagesArgs(BaseModel):
    consulta: str = Field(min_length=2, max_length=200)
    quantidade: int = Field(default=8, ge=1, le=12)


class SearchProductsArgs(BaseModel):
    texto: str | None = Field(default=None, max_length=100)
    status: ProductStatus | None = None


class OrdersArgs(BaseModel):
    status: str | None = Field(default=None, max_length=30)


class PieceArgs(BaseModel):
    imagem_id: str = Field(min_length=8, max_length=64)
    modo: PhotoMode
    tamanho_mm: float = Field(default=120, ge=20, le=3000)


class ProductChangeArgs(BaseModel):
    produto_id: int = Field(gt=0)
    titulo: str | None = Field(default=None, min_length=1, max_length=200)
    descricao: str | None = Field(default=None, max_length=5000)
    status: ProductStatus | None = None


# --- saída para o painel -----------------------------------------------------------------------
class ImageCard(BaseModel):
    number: int
    id: str
    title: str
    thumbnail: str
    creator: str
    license: str
    source_page: str


class Proposal(BaseModel):
    id: str
    tool: str
    summary: str


class AgentReply(BaseModel):
    reply: str
    memo: str  # o que o painel guarda na conversa (resposta + imagens mostradas)
    images: list[ImageCard] = []
    proposals: list[Proposal] = []


class ConfirmResult(BaseModel):
    message: str
    job: str | None = None  # "fila:<id>" (worker) ou "ia:<id>" (objeto 3D)
    product_id: int | None = None


@dataclass
class _Run:
    session: AsyncSession
    images: ImageSearch
    shown: list[ImageHit] = field(default_factory=list)
    proposals: list[Proposal] = field(default_factory=list)


async def _model(session: AsyncSession) -> str:
    settings = await effective_settings(session)
    if settings.api_key is None or not settings.api_key.get_secret_value():
        raise AINotConfiguredError("IA sem chave: cole em Integrações")
    for task in (AITask.PERSONALIZER, AITask.DEFAULT):
        try:
            return settings.model_for(task)
        except RuntimeError:
            continue
    raise AINotConfiguredError("escolha um modelo na tela IA")


async def _search_images(run: _Run, args: SearchImagesArgs) -> dict[str, Any]:
    hits = await run.images.search(args.consulta, args.quantidade)
    start = len(run.shown)
    run.shown.extend(hits)
    return {
        "imagens": [
            {"numero": start + i + 1, "id": h.id, "titulo": h.title, "licenca": h.license}
            for i, h in enumerate(hits)
        ]
        or "nenhuma imagem encontrada; tente outra consulta em inglês"
    }


async def _search_products(run: _Run, args: SearchProductsArgs) -> dict[str, Any]:
    stmt = select(Product).order_by(Product.updated_at.desc()).limit(15)
    if args.texto:
        like = f"%{args.texto}%"
        stmt = stmt.where(or_(Product.title.ilike(like), Product.category.ilike(like)))
    if args.status:
        stmt = stmt.where(Product.status == args.status)
    products = (await run.session.scalars(stmt)).all()
    return {
        "produtos": [
            {
                "id": p.id,
                "titulo": p.title,
                "nicho": p.niche,
                "status": p.status,
                "guardiao": p.guardian_status,
            }
            for p in products
        ]
        or "nenhum produto encontrado"
    }


async def _orders(run: _Run, args: OrdersArgs) -> dict[str, Any]:
    counts = (
        await run.session.execute(select(Order.status, func.count()).group_by(Order.status))
    ).all()
    stmt = select(Order).order_by(Order.id.desc()).limit(10)
    if args.status:
        stmt = stmt.where(Order.status == args.status)
    recent = (await run.session.scalars(stmt)).all()
    return {
        "por_status": dict(Counter({s: int(n) for s, n in counts})),
        "ultimos": [
            {"numero": o.number, "status": o.status, "canal": o.channel, "total": str(o.total)}
            for o in recent
        ],
    }


async def _propose(run: _Run, tool: str, args: BaseModel, summary: str, redis: ArqRedis) -> str:
    pid = secrets.token_hex(8)
    payload = json.dumps({"tool": tool, "args": args.model_dump()})
    await redis.set(PROPOSAL_KEY.format(pid), payload, ex=PROPOSAL_TTL)
    run.proposals.append(Proposal(id=pid, tool=tool, summary=summary))
    return f"proposta criada (aguarda o dono confirmar): {summary}"


def _piece_summary(args: PieceArgs, hit: ImageHit | None) -> str:
    what = {
        "litofania": "litofania",
        "placa_multicor": "placa multicor",
        "cortador": "cortador de biscoito",
        "chaveiro_silhueta": "chaveiro de silhueta",
        "objeto_3d": "objeto 3D por IA (gasta créditos da Meshy)",
    }[args.modo]
    title = f'"{hit.title}"' if hit else f"imagem {args.imagem_id}"
    return f"Gerar {what} de {title}, {args.tamanho_mm:.0f} mm"


async def _call(run: _Run, redis: ArqRedis, call: admin_agent.ToolCall) -> str:
    try:
        raw = json.loads(call.argumentos_json or "{}")
        if not isinstance(raw, dict):
            raise ValueError("argumentos precisam ser um objeto JSON")
        if call.ferramenta == "buscar_imagens":
            out: Any = await _search_images(run, SearchImagesArgs.model_validate(raw))
        elif call.ferramenta == "buscar_produtos":
            out = await _search_products(run, SearchProductsArgs.model_validate(raw))
        elif call.ferramenta == "resumo_pedidos":
            out = await _orders(run, OrdersArgs.model_validate(raw))
        elif call.ferramenta == "gerar_peca_da_imagem":
            piece = PieceArgs.model_validate(raw)
            hit = next((h for h in run.shown if h.id == piece.imagem_id), None)
            out = await _propose(run, call.ferramenta, piece, _piece_summary(piece, hit), redis)
        else:
            change = ProductChangeArgs.model_validate(raw)
            product = await run.session.get(Product, change.produto_id)
            if product is None:
                return f"[{call.ferramenta}] erro: produto {change.produto_id} não existe"
            fields = [
                f"{label} → {value!r}"
                for label, value in (
                    ("título", change.titulo),
                    ("descrição", change.descricao and change.descricao[:60] + "…"),
                    ("status", change.status),
                )
                if value
            ]
            if not fields:
                return f"[{call.ferramenta}] erro: nada para mudar"
            summary = f'Produto #{product.id} "{product.title}": ' + "; ".join(fields)
            out = await _propose(run, call.ferramenta, change, summary, redis)
    except (ValueError, ValidationError) as exc:
        return f"[{call.ferramenta}] erro nos argumentos: {str(exc)[:300]}"
    except ImageSearchError as exc:
        return f"[{call.ferramenta}] erro: {exc}"
    return f"[{call.ferramenta}] {json.dumps(out, ensure_ascii=False)[:4000]}"


def _memo(reply: str, shown: list[ImageHit]) -> str:
    """Resposta + imagens mostradas: o painel devolve isto na conversa ("faz da 2")."""
    if not shown:
        return reply
    listed = "; ".join(f"#{i + 1} id={h.id} {h.title[:40]}" for i, h in enumerate(shown))
    return f"{reply}\n[imagens mostradas: {listed}]"[:4000]


async def chat(
    session: AsyncSession,
    factory: ProviderFactory,
    images: ImageSearch,
    redis: ArqRedis,
    turns: list[admin_agent.Turn],
) -> AgentReply:
    model = await _model(session)
    settings = await effective_settings(session)
    provider = factory(settings)
    brand = await session.get(BrandSettings, SINGLETON_ID)
    run = _Run(session=session, images=images)
    results: list[str] = []
    reply = ""
    for _ in range(MAX_STEPS):
        system, prompt = admin_agent.build(
            loja=brand.name if brand else "a loja", turns=turns[-12:], results=results
        )
        step = await provider.complete_json(
            system=system,
            prompt=prompt,
            schema=admin_agent.AgentStep,
            model=model,
            max_tokens=2000,
        )
        reply = step.mensagem.strip()
        if not step.chamadas:
            break
        new = [await _call(run, redis, call) for call in step.chamadas]
        results.extend(new)
        only_proposals = all(c.ferramenta not in admin_agent.READ_TOOLS for c in step.chamadas)
        if only_proposals and not any("] erro" in r for r in new):
            break  # só propostas: a mensagem já fala do botão de confirmar
    cards = [
        ImageCard(
            number=i + 1,
            id=h.id,
            title=h.title,
            thumbnail=h.thumbnail,
            creator=h.creator,
            license=h.license,
            source_page=h.source_page,
        )
        for i, h in enumerate(run.shown)
    ]
    reply = reply or "Pronto."
    return AgentReply(
        reply=reply, memo=_memo(reply, run.shown), images=cards, proposals=run.proposals
    )


async def confirm(
    session: AsyncSession,
    storage: LocalStorage,
    redis: ArqRedis,
    images: ImageSearch,
    proposal_id: str,
) -> ConfirmResult:
    if not proposal_id.isalnum() or len(proposal_id) != 16:
        raise AgentError("proposta inválida")
    raw = await redis.getdel(PROPOSAL_KEY.format(proposal_id))
    if raw is None:
        raise AgentError("proposta expirou ou já foi usada: peça de novo ao assistente")
    saved = json.loads(raw)
    tool, args = saved["tool"], saved["args"]
    if tool == "gerar_peca_da_imagem":
        return await _make_piece(session, storage, redis, images, PieceArgs.model_validate(args))
    if tool == "alterar_produto":
        return await _change_product(session, ProductChangeArgs.model_validate(args))
    raise AgentError(f"ferramenta desconhecida: {tool}")


async def _make_piece(
    session: AsyncSession,
    storage: LocalStorage,
    queue: ArqRedis,
    images: ImageSearch,
    args: PieceArgs,
) -> ConfirmResult:
    try:
        hit = await images.get(args.imagem_id)
        image = await images.download(hit.url)
    except ImageSearchError as exc:
        raise AgentError(str(exc)) from exc
    reason = f"assistente: imagem {hit.license} de {hit.creator} ({hit.source_page})"[:300]
    if args.modo == "objeto_3d":
        provider = await integrations.image_to_3d(session)
        if provider is None:
            raise AgentError("cole a chave da Meshy em Integrações → Foto vira objeto 3D")
        try:
            ref = await photos.start_3d(
                session,
                storage,
                provider,
                data=image.data,
                mime=image.mime,
                ext=image.ext,
                size_mm=args.tamanho_mm,
                reason=reason,
            )
        except Image3DError as exc:
            raise AgentError(str(exc)) from exc
        return ConfirmResult(message=f"Enviei para a IA de 3D: {hit.title}", job=f"ia:{ref}")
    size_key = "width_mm" if args.modo in WIDTH_MODES else "size_mm"
    job_id = await photos.enqueue_part(
        session,
        storage,
        queue,
        data=image.data,
        ext=image.ext,
        mode=args.modo,
        params={size_key: args.tamanho_mm},
        reason=reason,
    )
    return ConfirmResult(message=f"Gerando a peça de: {hit.title}", job=f"fila:{job_id}")


async def _change_product(session: AsyncSession, args: ProductChangeArgs) -> ConfirmResult:
    changes = {"title": args.titulo, "description": args.descricao, "status": args.status}
    # só os campos que mudam: update_product usa exclude_unset (None apagaria o título)
    patch = ProductPatch.model_validate({k: v for k, v in changes.items() if v is not None})
    try:
        product = await catalog.update_product(session, args.produto_id, patch)
    except (catalog.NotFoundError, catalog.CatalogRuleError, UnknownNicheError) as exc:
        await session.rollback()
        raise AgentError(str(exc)) from exc
    await audit.record(
        session,
        actor="admin",
        action="assistente_alterou_produto",
        entity_type="produto",
        entity_id=product.id,
        reason="confirmado pelo dono no assistente do painel",
        payload=patch.model_dump(exclude_none=True),
    )
    await session.commit()
    note = (
        "" if product.guardian_status == "aprovado" else f" (Guardião: {product.guardian_status})"
    )
    return ConfirmResult(
        message=f'Produto #{product.id} "{product.title}" atualizado{note}.',
        product_id=product.id,
    )
