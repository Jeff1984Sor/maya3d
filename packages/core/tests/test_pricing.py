from decimal import Decimal as D

import pytest

from print3d_core.pricing import (
    CostInputs,
    FeeBand,
    PricingError,
    ProfitRule,
    compute_cost,
    psychological,
    quote_channel,
)

# Faixas FICTÍCIAS só para teste (tarifas reais vêm da API/tabela, nunca do código).
ML_LIKE = [
    FeeBand(D("0"), D("79"), D("0.12"), D("6.75")),
    FeeBand(D("79"), None, D("0.12"), D("0")),
]
PIX_LIKE = [FeeBand(D("0"), None, D("0.0099"))]
RULE = ProfitRule(min_profit=D("8"), margin=D("0.40"))


def _inputs(**over: object) -> CostInputs:
    base: dict[str, object] = {
        "grams_by_material": {"pla-branco": D("50")},
        "price_per_kg": {"pla-branco": D("100")},
        "print_hours": D("2"),
        "printer_watts": D("120"),
        "energy_price_kwh": D("1.00"),
        "printer_hourly_wear": D("0.50"),
        "post_minutes": D("10"),
        "labor_per_hour": D("30"),
        "failure_rate": D("0.10"),
    }
    base.update(over)
    return CostInputs(**base)  # type: ignore[arg-type]


def test_custo_segue_a_formula_da_spec() -> None:
    c = compute_cost(_inputs())
    # material 50gxR$0,10=5,00 | energia 0,12kWx2hx1,00=0,24 | desgaste 2x0,50=1,00
    # mão de obra 10minxR$0,50=5,00 | direto 11,24 | falha 10% = 1,124 | total 12,364 → 12,36
    assert (c.material, c.energy, c.wear, c.labor) == (D("5.00"), D("0.24"), D("1.00"), D("5.00"))
    assert c.failure == D("1.12")
    assert c.total == D("12.36")


def test_extras_nao_sofrem_taxa_de_falha() -> None:
    c = compute_cost(_inputs(extra_costs=D("2.00")))
    assert c.total == D("14.36")
    assert c.base == D("12.36")


def test_multicor_soma_materiais() -> None:
    c = compute_cost(
        _inputs(
            grams_by_material={"branco": D("40"), "preto": D("5")},
            price_per_kg={"branco": D("100"), "preto": D("120")},
        )
    )
    assert c.material == D("4.60")


@pytest.mark.parametrize(
    "over",
    [
        {"grams_by_material": {}},
        {"grams_by_material": {"x": D("1")}},  # sem preço
        {"failure_rate": D("1")},
    ],
)
def test_custo_rejeita_dados_invalidos(over: dict[str, object]) -> None:
    with pytest.raises(PricingError):
        compute_cost(_inputs(**over))


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("20.5636", "20.90"), ("20.95", "21.90"), ("20.90", "20.90"), ("20", "20.90")],
)
def test_arredondamento_psicologico(valor: str, esperado: str) -> None:
    assert psychological(D(valor)) == D(esperado)


def test_site_pix_lucro_minimo() -> None:
    q = quote_channel("site_pix", D("12.36"), PIX_LIKE, RULE)
    # alvo = max(8, 4,94) = 8 → (12,36+8)/0,9901 = 20,56 → 20,90
    assert q.price == D("20.90")
    assert q.net_profit >= D("8")


def test_faixa_alta_quando_lucro_nao_cabe_na_baixa() -> None:
    q = quote_channel("ml_classico", D("60"), ML_LIKE, RULE)
    # alvo 24; faixa <79 daria 103,13 (fora); faixa >=79: 84/0,88 = 95,45 → 95,90
    assert q.price == D("95.90")
    assert q.fixed_fee == D("0")
    assert q.net_profit >= D("24")


def test_escolhe_a_faixa_mais_barata() -> None:
    q = quote_channel("ml_classico", D("50"), ML_LIKE, ProfitRule(D("8"), D("0.10")))
    # faixa <79: (50+8+6,75)/0,88 = 73,58 → 73,90 | faixa >=79: piso 79 → 79,90. Vence 73,90.
    assert q.price == D("73.90")
    assert q.fixed_fee == D("6.75")
    assert q.net_profit >= D("8")


def test_frete_assumido_entra_no_preco() -> None:
    sem = quote_channel("site_pix", D("12.36"), PIX_LIKE, RULE)
    com = quote_channel("site_pix", D("12.36"), PIX_LIKE, RULE, shipping=D("10"))
    assert com.price > sem.price
    assert com.net_profit >= D("8")


def test_sem_faixas_erro_claro() -> None:
    with pytest.raises(PricingError, match="nenhuma faixa"):
        quote_channel("shopee", D("10"), [], RULE)


def test_arredondamento_que_cruza_faixa_reconfere_lucro() -> None:
    # Faixa baixa sem tarifa até 30; acima de 30 comissão de 50%. Preço bruto 29,95 → ,90 = 30,90
    # cairia na faixa cara e perderia lucro; o motor precisa subir até recuperar o alvo.
    bands = [FeeBand(D("0"), D("30"), D("0")), FeeBand(D("30"), None, D("0.50"))]
    q = quote_channel("x", D("21.95"), bands, ProfitRule(D("8"), D("0")))
    assert q.net_profit >= D("8")
