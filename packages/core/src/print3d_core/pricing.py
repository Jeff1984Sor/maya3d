"""Motor de precificação (spec seção 2 — Precificação). Puro: sem banco, sem rede.

Custo:
    material   = gramas x custo_por_grama            (gramas vêm do fatiador)
    energia    = (W / 1000) x horas x tarifa_kWh
    desgaste   = horas x custo_hora_impressora
    mao_obra   = minutos_pos x custo_minuto
    custo_base = (material + energia + desgaste + mao_obra) x (1 + taxa_falha)
    custo_total = custo_base + extras                 (embalagem, argola, ímã: não sofrem falha)

Preço por canal (de trás pra frente), para cada faixa de tarifa do canal:
    preco = (custo_total + lucro + taxa_fixa + frete) / (1 - comissao)
    lucro = max(lucro_minimo, custo_total x margem)
A faixa depende do próprio preço (ex.: taxa fixa abaixo de certo valor), então testamos todas
as faixas e ficamos com o menor preço válido. Tarifas NUNCA ficam no código: entram como FeeBand.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
_ZERO = Decimal("0")
_MAX_ROUNDING_STEPS = 200


class PricingError(Exception):
    """Dados insuficientes ou inconsistentes para precificar."""


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def ceil_cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_CEILING)


def psychological(value: Decimal) -> Decimal:
    """Menor preço terminado em ,90 que seja >= value (20,57 → 20,90; 20,95 → 21,90)."""
    candidate = value.to_integral_value(rounding="ROUND_FLOOR") + Decimal("0.90")
    return candidate if candidate >= value else candidate + 1


@dataclass(frozen=True)
class CostInputs:
    grams_by_material: Mapping[str, Decimal]
    price_per_kg: Mapping[str, Decimal]
    print_hours: Decimal
    printer_watts: Decimal
    energy_price_kwh: Decimal
    printer_hourly_wear: Decimal
    post_minutes: Decimal
    labor_per_hour: Decimal
    failure_rate: Decimal
    extra_costs: Decimal = _ZERO


@dataclass(frozen=True)
class CostBreakdown:
    material: Decimal
    energy: Decimal
    wear: Decimal
    labor: Decimal
    failure: Decimal
    extras: Decimal
    total: Decimal

    @property
    def base(self) -> Decimal:
        return self.total - self.extras


def compute_cost(inputs: CostInputs) -> CostBreakdown:
    missing = set(inputs.grams_by_material) - set(inputs.price_per_kg)
    if missing:
        raise PricingError(f"material sem preço por kg: {sorted(missing)}")
    if not inputs.grams_by_material:
        raise PricingError("sem gramas de material (fatie a peça ou informe manualmente)")
    if any(v < 0 for v in inputs.grams_by_material.values()):
        raise PricingError("gramas negativas")
    if not (_ZERO <= inputs.failure_rate < 1):
        raise PricingError("taxa de falha deve estar em [0, 1)")

    material = sum(
        (g / 1000 * inputs.price_per_kg[m] for m, g in inputs.grams_by_material.items()), _ZERO
    )
    energy = inputs.printer_watts / 1000 * inputs.print_hours * inputs.energy_price_kwh
    wear = inputs.print_hours * inputs.printer_hourly_wear
    labor = inputs.post_minutes * inputs.labor_per_hour / 60
    direct = material + energy + wear + labor
    failure = direct * inputs.failure_rate
    total = money(direct + failure + inputs.extra_costs)
    return CostBreakdown(
        material=money(material),
        energy=money(energy),
        wear=money(wear),
        labor=money(labor),
        failure=money(failure),
        extras=money(inputs.extra_costs),
        total=total,
    )


@dataclass(frozen=True)
class FeeBand:
    """Faixa de tarifa de um canal: vale para min_price <= preço < max_price."""

    min_price: Decimal
    max_price: Decimal | None
    commission_rate: Decimal  # 0.12 = 12%
    fixed_fee: Decimal = _ZERO

    def contains(self, price: Decimal) -> bool:
        return price >= self.min_price and (self.max_price is None or price < self.max_price)


@dataclass(frozen=True)
class ProfitRule:
    min_profit: Decimal  # lucro mínimo em R$ por peça
    margin: Decimal  # margem sobre o custo (0.40 = 40%)

    def target(self, cost: Decimal) -> Decimal:
        return max(self.min_profit, cost * self.margin)


@dataclass(frozen=True)
class ChannelQuote:
    channel: str
    price: Decimal
    commission: Decimal
    fixed_fee: Decimal
    shipping: Decimal
    net_profit: Decimal
    band: FeeBand


def net_profit(price: Decimal, cost: Decimal, band: FeeBand, shipping: Decimal) -> Decimal:
    return price - price * band.commission_rate - band.fixed_fee - shipping - cost


def _band_for(price: Decimal, bands: Sequence[FeeBand]) -> FeeBand | None:
    return next((b for b in bands if b.contains(price)), None)


def quote_channel(
    channel: str,
    cost: Decimal,
    bands: Sequence[FeeBand],
    rule: ProfitRule,
    *,
    shipping: Decimal = _ZERO,
    round_psychological: bool = True,
) -> ChannelQuote:
    """Menor preço que garante o lucro alvo em `channel`, já arredondado."""
    if not bands:
        raise PricingError(f"canal {channel}: nenhuma faixa de tarifa cadastrada")
    target = rule.target(cost)
    best: ChannelQuote | None = None

    for band in bands:
        if band.commission_rate >= 1:
            continue
        raw = (cost + target + band.fixed_fee + shipping) / (1 - band.commission_rate)
        if band.max_price is not None and raw >= band.max_price:
            continue  # esta faixa não comporta o lucro; outra faixa resolve
        raw = max(raw, band.min_price)  # abaixo da faixa: o piso dela ainda pode ser o mais barato
        price = psychological(raw) if round_psychological else ceil_cents(raw)

        # O arredondamento pode empurrar o preço para outra faixa: reconfere o lucro na faixa final.
        step = Decimal(1) if round_psychological else CENT
        for _ in range(_MAX_ROUNDING_STEPS):
            final_band = _band_for(price, bands)
            if final_band is not None and net_profit(price, cost, final_band, shipping) >= target:
                break
            price += step
        else:
            continue

        assert final_band is not None
        quote = ChannelQuote(
            channel=channel,
            price=price,
            commission=money(price * final_band.commission_rate),
            fixed_fee=final_band.fixed_fee,
            shipping=shipping,
            net_profit=money(net_profit(price, cost, final_band, shipping)),
            band=final_band,
        )
        if best is None or quote.price < best.price:
            best = quote

    if best is None:
        raise PricingError(f"canal {channel}: nenhuma faixa comporta o lucro mínimo")
    return best
