"""Liga o motor de preço (print3d_core.pricing) aos dados do banco."""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.models import ChannelFeeBand, CostConfig, Material, Printer
from print3d_api.models.pricing import COST_CONFIG_ID
from print3d_api.schemas.pricing import (
    ChannelQuoteOut,
    CompareRequest,
    CompareResponse,
    CompareRow,
    CostOut,
    QuoteRequest,
    QuoteResponse,
)
from print3d_core import (
    CostInputs,
    FeeBand,
    PricingError,
    ProfitRule,
    compute_cost,
    quote_channel,
)
from print3d_core.materials import convert_grams, density_for
from print3d_core.pricing import money


class QuoteInputError(Exception):
    """Entrada inválida para cotação (vira 422/404 na rota)."""

    def __init__(self, message: str, *, not_found: bool = False) -> None:
        super().__init__(message)
        self.not_found = not_found


def select_bands(bands: Iterable[ChannelFeeBand], category: str | None) -> dict[str, list[FeeBand]]:
    """Por canal: usa as faixas da categoria, se existirem; senão as genéricas (category NULL)."""
    by_channel: dict[str, list[ChannelFeeBand]] = defaultdict(list)
    for band in bands:
        by_channel[band.channel].append(band)

    selected: dict[str, list[FeeBand]] = {}
    for channel, rows in by_channel.items():
        specific = [b for b in rows if category is not None and b.category == category]
        chosen = specific or [b for b in rows if b.category is None]
        selected[channel] = [
            FeeBand(b.min_price, b.max_price, b.commission_rate, b.fixed_fee)
            for b in sorted(chosen, key=lambda b: b.min_price)
        ]
    return selected


def margin_for(config: CostConfig, category: str | None) -> Decimal:
    if category and category in config.margin_by_category:
        return Decimal(config.margin_by_category[category])
    return config.default_margin


def _warnings(printer: Printer, materials: Sequence[Material]) -> list[str]:
    out: list[str] = []
    if printer.status != "ativa":
        out.append(f"impressora '{printer.name}' está {printer.status}")
    for m in materials:
        if not m.active:
            out.append(f"material {m.kind} {m.color_name} está inativo")
        if printer.supported_materials and m.kind not in printer.supported_materials:
            out.append(f"impressora '{printer.name}' não imprime {m.kind}")
        if m.kind == "ASA" and not printer.enclosed:
            out.append("ASA exige impressora fechada")
    return out


async def quote(session: AsyncSession, req: QuoteRequest) -> QuoteResponse:
    printer = await session.get(Printer, req.printer_id)
    if printer is None:
        raise QuoteInputError(f"impressora {req.printer_id} não existe", not_found=True)
    config = await session.get(CostConfig, COST_CONFIG_ID)
    if config is None:
        raise QuoteInputError("cost_config ausente (rode as migrações)")

    ids = list(req.grams_by_material)
    materials = (await session.scalars(select(Material).where(Material.id.in_(ids)))).all()
    missing = set(ids) - {m.id for m in materials}
    if missing:
        raise QuoteInputError(f"materiais inexistentes: {sorted(missing)}", not_found=True)

    hours = Decimal(req.print_minutes) / 60
    try:
        cost = compute_cost(
            CostInputs(
                grams_by_material={str(k): v for k, v in req.grams_by_material.items()},
                price_per_kg={str(m.id): m.price_per_kg for m in materials},
                print_hours=hours,
                printer_watts=Decimal(printer.avg_watts),
                energy_price_kwh=config.energy_price_kwh,
                printer_hourly_wear=printer.hourly_wear,
                post_minutes=Decimal(req.post_minutes),
                labor_per_hour=config.labor_per_hour,
                failure_rate=config.failure_rate,
                extra_costs=req.extra_costs,
            )
        )
    except PricingError as exc:
        raise QuoteInputError(str(exc)) from exc

    rule = ProfitRule(config.min_profit, margin_for(config, req.category))
    stmt = select(ChannelFeeBand)
    if req.channels:
        stmt = stmt.where(ChannelFeeBand.channel.in_(req.channels))
    bands = select_bands((await session.scalars(stmt)).all(), req.category)

    quotes: list[ChannelQuoteOut] = []
    for channel in req.channels or sorted(bands):
        shipping = req.shipping_by_channel.get(channel, Decimal(0))
        try:
            q = quote_channel(channel, cost.total, bands.get(channel, []), rule, shipping=shipping)
        except PricingError as exc:
            quotes.append(ChannelQuoteOut(channel=channel, shipping=shipping, error=str(exc)))
            continue
        quotes.append(
            ChannelQuoteOut(
                channel=channel,
                price=q.price,
                commission=q.commission,
                fixed_fee=q.fixed_fee,
                shipping=q.shipping,
                net_profit=q.net_profit,
                margin_pct=money(q.net_profit / q.price * 100),
            )
        )

    return QuoteResponse(
        cost=CostOut(**cost.__dict__),
        target_profit=money(rule.target(cost.total)),
        quotes=quotes,
        warnings=_warnings(printer, materials),
    )


async def compare(session: AsyncSession, req: CompareRequest) -> CompareResponse:
    """A mesma peça em cada material: gramas ajustadas pela densidade, custo e preço por canal.

    Tempo de impressão é mantido (aproximação; o fatiador por material refina na Fase 1B).
    """
    ref_kind, ref_density, ref_label = req.reference_kind.upper(), None, req.reference_kind.upper()
    if req.reference_material_id is not None:
        ref = await session.get(Material, req.reference_material_id)
        if ref is None:
            raise QuoteInputError(
                f"material {req.reference_material_id} não existe", not_found=True
            )
        ref_kind, ref_density = ref.kind, ref.density_g_cm3
        ref_label = f"{ref.kind} {ref.color_name}"
    from_density = density_for(ref_kind, ref_density)

    stmt = select(Material).order_by(Material.kind, Material.color_name)
    stmt = (
        stmt.where(Material.id.in_(req.material_ids))
        if req.material_ids
        else stmt.where(Material.active)
    )
    rows: list[CompareRow] = []
    for material in (await session.scalars(stmt)).all():
        density = density_for(material.kind, material.density_g_cm3)
        grams = convert_grams(req.grams, from_density, density)
        result = await quote(
            session,
            QuoteRequest(
                grams_by_material={material.id: grams},
                print_minutes=req.print_minutes,
                printer_id=req.printer_id,
                post_minutes=req.post_minutes,
                category=req.category,
                extra_costs=req.extra_costs,
                channels=req.channels,
            ),
        )
        priced = [q for q in result.quotes if q.price is not None]
        best = min(priced, key=lambda q: q.price or Decimal(0), default=None)
        rows.append(
            CompareRow(
                material_id=material.id,
                label=f"{material.kind} {material.color_name}"
                + (f" ({material.brand})" if material.brand else ""),
                kind=material.kind,
                color_hex=material.color_hex,
                density=density,
                grams=grams,
                cost=result.cost,
                quotes=result.quotes,
                warnings=result.warnings,
                best_price=best.price if best else None,
                best_profit=best.net_profit if best else None,
            )
        )
    rows.sort(key=lambda r: r.cost.total)
    return CompareResponse(reference=ref_label, reference_grams=req.grams, rows=rows)
