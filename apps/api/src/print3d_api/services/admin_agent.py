"""🤖 Assistente do painel: conversa com o dono e usa ferramentas do sistema.

Consulta (buscar imagens, produtos, pedidos) roda na hora. O que altera algo vira PROPOSTA
guardada no Redis por 1 hora e só roda quando o dono confirma (auditoria registra).
"""

import json
import re
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
from print3d_api.schemas.governance import GuardianCheckIn
from print3d_api.services import audit, catalog, guardian, integrations, photos
from print3d_api.services.ai import ProviderFactory, effective_settings
from print3d_api.services.guardian import UnknownNicheError
from print3d_core.storage import LocalStorage
from print3d_mesh.custom import FONT_NAMES, CustomPart, CustomScadError, validate
from print3d_mesh.image3d import Image3DError
from print3d_mesh.parametric import MODELS

MAX_STEPS = 5
PROPOSAL_TTL = 3600
PROPOSAL_KEY = "agente:proposta:{}"
PhotoMode = Literal["litofania", "placa_multicor", "cortador", "chaveiro_silhueta", "objeto_3d"]
WIDTH_MODES = ("litofania", "placa_multicor")  # nesses, o tamanho é a largura
# a IA falou em botão sem criar proposta: corrige uma vez (o dono via um botão que não existia)
_PROMISES_BUTTON = re.compile(r"bot[aã]o|confirm", re.IGNORECASE)
_NO_BUTTON = (
    "[sistema] Você falou em botão/confirmar, mas NÃO chamou nenhuma ferramenta de alteração, "
    "então não existe botão. Chame agora a ferramenta certa (ex.: listar_parametricos e "
    "gerar_parametrico) ou diga com honestidade o que não dá para fazer."
)


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


class ParametricArgs(BaseModel):
    modelo: str = Field(min_length=2, max_length=60)
    parametros: dict[str, Any] = {}


class CustomPartArgs(BaseModel):
    nome: str = Field(min_length=1, max_length=24)
    scad: str = Field(min_length=5, max_length=12_000)


class CustomPieceArgs(BaseModel):
    nome: str = Field(min_length=2, max_length=80)
    partes: list[CustomPartArgs] = Field(min_length=1, max_length=4)


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


class JobCard(BaseModel):
    job: str  # "fila:<id>"
    title: str


class AgentReply(BaseModel):
    reply: str
    memo: str  # o que o painel guarda na conversa (resposta + imagens + código das peças)
    images: list[ImageCard] = []
    proposals: list[Proposal] = []
    jobs: list[JobCard] = []


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
    jobs: list[JobCard] = field(default_factory=list)
    created: list[str] = field(default_factory=list)  # código das peças criadas (memo)


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


def _list_parametric() -> dict[str, Any]:
    """Modelos e parâmetros (nome, opções, padrão, limites) em formato curto para a IA."""
    out = []
    for m in MODELS.values():
        params = {}
        for name, prop in m.params_model.model_json_schema().get("properties", {}).items():
            options = prop.get("enum") or [
                o["const"] for o in prop.get("anyOf", []) if "const" in o
            ]
            info = {"titulo": prop.get("title"), "padrao": prop.get("default")}
            if options:
                info["opcoes"] = options
            for key, label in (("minimum", "min"), ("maximum", "max"), ("maxLength", "letras")):
                if key in prop:
                    info[label] = prop[key]
            params[name] = info
        out.append(
            {"modelo": m.slug, "titulo": m.title, "descricao": m.description, "parametros": params}
        )
    return {"modelos": out}


async def _check_texts(session: AsyncSession, slug: str, parsed: BaseModel) -> str | None:
    """Texto livre da peça passa pelo Guardião (palavrão, marca, time...). None = aprovado."""
    model = MODELS[slug]
    texts = [str(v) for k in model.text_fields if (v := getattr(parsed, k, None))]
    if not texts:
        return None
    verdict = await guardian.check(
        session,
        GuardianCheckIn(
            niche=model.niche, title=model.title, origin="parametrico", customer_text=texts
        ),
    )
    return None if verdict.approved else "; ".join(v.message for v in verdict.violations)


async def _propose_parametric(run: _Run, redis: ArqRedis, args: ParametricArgs) -> str:
    model = MODELS.get(args.modelo)
    if model is None:
        return f"erro: modelo '{args.modelo}' não existe; use listar_parametricos"
    parsed = model.parse(args.parametros)  # ValidationError volta para a IA corrigir
    refused = await _check_texts(run.session, args.modelo, parsed)
    if refused:
        return f"erro: texto recusado pelo Guardião: {refused}"
    shown = ", ".join(f"{k}={v}" for k, v in args.parametros.items())
    summary = f'Gerar "{model.title}": {shown}'
    saved = ParametricArgs(modelo=args.modelo, parametros=parsed.model_dump(mode="json"))
    return await _propose(run, "gerar_parametrico", saved, summary, redis)


async def _create_piece(run: _Run, queue: ArqRedis, args: CustomPieceArgs) -> str:
    """Peça desenhada pela IA: confere o código, passa os textos no Guardião e já gera."""
    parts = [CustomPart(name=p.nome, scad=p.scad) for p in args.partes]
    try:
        texts = validate(parts)
    except CustomScadError as exc:
        return f"erro: {exc}"
    if texts:
        verdict = await guardian.check(
            run.session,
            GuardianCheckIn(
                niche="brindes", title=args.nome, origin="parametrico", customer_text=texts
            ),
        )
        if not verdict.approved:
            return "erro: texto recusado pelo Guardião: " + "; ".join(
                v.message for v in verdict.violations
            )
    job = await queue.enqueue_job(
        "generate_custom_scad", [{"name": p.name, "scad": p.scad} for p in parts]
    )
    if job is None:
        return "erro: job duplicado"
    await audit.record(
        run.session,
        actor="admin",
        action="assistente_criou_peca",
        entity_type="peca_sob_medida",
        entity_id=job.job_id,
        reason=args.nome[:200],
        payload={"partes": [p.name for p in parts]},
    )
    await run.session.commit()
    run.jobs.append(JobCard(job=f"fila:{job.job_id}", title=args.nome))
    code = "\n".join(f"// parte {p.name}\n{p.scad}" for p in parts)
    run.created.append(f"[peça criada: {args.nome}]\n{code}")
    return "peça enviada para gerar; o dono vê a prévia 3D abaixo da sua mensagem"


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
        elif call.ferramenta == "listar_parametricos":
            out = _list_parametric()
        elif call.ferramenta == "gerar_parametrico":
            proposed = await _propose_parametric(run, redis, ParametricArgs.model_validate(raw))
            if proposed.startswith("erro"):
                return f"[{call.ferramenta}] {proposed}"
            out = proposed
        elif call.ferramenta == "criar_peca":
            created = await _create_piece(run, redis, CustomPieceArgs.model_validate(raw))
            if created.startswith("erro"):
                return f"[{call.ferramenta}] {created}"
            out = created
        elif call.ferramenta == "gerar_peca_da_imagem":
            piece = PieceArgs.model_validate(raw)
            hit = next((h for h in run.shown if h.id == piece.imagem_id), None)
            out = await _propose(run, call.ferramenta, piece, _piece_summary(piece, hit), redis)
        elif call.ferramenta == "alterar_produto":
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
        else:
            return f"[{call.ferramenta}] erro: ferramenta desconhecida"
    except (ValueError, ValidationError) as exc:
        return f"[{call.ferramenta}] erro nos argumentos: {str(exc)[:300]}"
    except ImageSearchError as exc:
        return f"[{call.ferramenta}] erro: {exc}"
    return f"[{call.ferramenta}] {json.dumps(out, ensure_ascii=False)[:9000]}"


def _memo(reply: str, shown: list[ImageHit], created: list[str]) -> str:
    """Resposta + imagens mostradas + código das peças: o painel devolve isto na conversa
    ("faz da 2", "aumenta o texto")."""
    memo = reply
    if shown:
        listed = "; ".join(f"#{i + 1} id={h.id} {h.title[:40]}" for i, h in enumerate(shown))
        memo += f"\n[imagens mostradas: {listed}]"
    for code in created:
        memo += f"\n{code}"
    return memo[:16000]


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
    corrected = False
    for _ in range(MAX_STEPS):
        system, prompt = admin_agent.build(
            loja=brand.name if brand else "a loja",
            turns=turns[-12:],
            results=results,
            fonts=sorted(FONT_NAMES),
        )
        step = await provider.complete_json(
            system=system,
            prompt=prompt,
            schema=admin_agent.AgentStep,
            model=model,
            max_tokens=8000,  # o passo pode trazer o código OpenSCAD de uma peça
        )
        reply = step.mensagem.strip()
        if not step.chamadas:
            if run.proposals or run.jobs or corrected or not _PROMISES_BUTTON.search(reply):
                break
            corrected = True
            results.append(_NO_BUTTON)
            continue
        new = [await _call(run, redis, call) for call in step.chamadas]
        results.extend(new)
        only_proposals = all(c.ferramenta not in admin_agent.READ_TOOLS for c in step.chamadas)
        if only_proposals and not any("] erro" in r for r in new):
            break  # só propostas/peças: a IA não vê o resultado, o dono vê
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
        reply=reply,
        memo=_memo(reply, run.shown, run.created),
        images=cards,
        proposals=run.proposals,
        jobs=run.jobs,
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
    if tool == "gerar_parametrico":
        return await _make_parametric(session, redis, ParametricArgs.model_validate(args))
    raise AgentError(f"ferramenta desconhecida: {tool}")


async def _make_parametric(
    session: AsyncSession, queue: ArqRedis, args: ParametricArgs
) -> ConfirmResult:
    model = MODELS.get(args.modelo)
    if model is None:
        raise AgentError(f"modelo '{args.modelo}' não existe")
    try:
        parsed = model.parse(args.parametros)
    except ValidationError as exc:
        raise AgentError(f"parâmetros inválidos: {exc.errors(include_url=False)[:3]}") from exc
    refused = await _check_texts(session, args.modelo, parsed)
    if refused:
        raise AgentError(f"texto recusado pelo Guardião: {refused}")
    job = await queue.enqueue_job("generate_parametric", args.modelo, parsed.model_dump())
    if job is None:
        raise AgentError("job duplicado")
    await audit.record(
        session,
        actor="admin",
        action="assistente_gerou_parametrico",
        entity_type="parametrico",
        entity_id=job.job_id,
        reason="confirmado pelo dono no assistente do painel",
        payload={"modelo": args.modelo, "parametros": parsed.model_dump(mode="json")},
    )
    await session.commit()
    return ConfirmResult(message=f"Gerando {model.title}", job=f"fila:{job.job_id}")


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
