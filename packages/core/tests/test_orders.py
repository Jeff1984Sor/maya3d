from itertools import pairwise

import pytest

from print3d_core.orders import (
    CUSTOMER_LABELS,
    NEXT_STEP,
    TRANSITIONS,
    OrderStatus,
    TransitionError,
    check_transition,
    fingerprint,
    material_key,
    needs_sample,
)


def test_fluxo_normal() -> None:
    path = ["pago", "na_fila", "imprimindo", "acabamento", "embalado", "enviado", "entregue"]
    for cur, nxt in pairwise(path):
        assert check_transition(cur, nxt) == OrderStatus(nxt)


def test_fluxo_de_amostra_com_ajuste() -> None:
    path = [
        "pago",
        "imprimindo_amostra",
        "amostra_pronta",
        "ajuste_solicitado",
        "imprimindo_amostra",
        "amostra_pronta",
        "na_fila",
    ]
    for cur, nxt in pairwise(path):
        check_transition(cur, nxt)


@pytest.mark.parametrize(
    ("cur", "nxt"),
    [("pago", "enviado"), ("entregue", "na_fila"), ("imprimindo", "cancelado"), ("x", "pago")],
)
def test_transicoes_proibidas(cur: str, nxt: str) -> None:
    with pytest.raises(TransitionError):
        check_transition(cur, nxt)


def test_tabelas_completas() -> None:
    assert set(TRANSITIONS) == set(OrderStatus)
    assert set(CUSTOMER_LABELS) == set(OrderStatus)
    for cur, nxt in NEXT_STEP.items():
        assert nxt in TRANSITIONS[cur]


def test_regra_de_amostra() -> None:
    assert needs_sample(25, 10, already_produced=False)
    assert not needs_sample(10, 10, already_produced=False)  # "maior que 10"
    assert not needs_sample(25, 10, already_produced=True)  # pedido igual já aprovado antes


def test_impressao_digital_estavel_e_sensivel() -> None:
    a = fingerprint(7, {"nome": "Ana", "cor": "azul"}, [3, 1])
    assert a == fingerprint(7, {"cor": "azul", "nome": "Ana"}, [1, 3])  # ordem não importa
    assert a != fingerprint(7, {"nome": "Ana Clara", "cor": "azul"}, [1, 3])
    assert a != fingerprint(7, {"nome": "Ana", "cor": "azul"}, [1, 4])
    assert len(a) == 64


def test_chave_de_material() -> None:
    assert material_key([3, 1, 3]) == "1+3"
    assert material_key([]) == "sem-material"


def test_loja_aguarda_pagamento_antes_de_produzir() -> None:
    check_transition("aguardando_pagamento", "pago")
    check_transition("aguardando_pagamento", "cancelado")
    with pytest.raises(TransitionError):
        check_transition("aguardando_pagamento", "na_fila")
