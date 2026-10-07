from decimal import Decimal as D

import pytest

from print3d_core.materials import DEFAULT_DENSITY_G_CM3, convert_grams, density_for


def test_mesma_peca_em_outro_material() -> None:
    # 50 g de PLA (1,24) viram ~51,2 g em PETG (1,27) e ~43,1 g em ASA (1,07)
    assert convert_grams(D("50"), D("1.24"), D("1.27")) == D("51.2")
    assert convert_grams(D("50"), D("1.24"), D("1.07")) == D("43.1")
    assert convert_grams(D("50"), D("1.24"), D("1.24")) == D("50.0")


def test_densidade_do_cadastro_tem_prioridade() -> None:
    assert density_for("PLA") == D("1.24")
    assert density_for("pla", D("1.30")) == D("1.30")
    assert density_for("DESCONHECIDO") == DEFAULT_DENSITY_G_CM3["PLA"]
    assert density_for("PETG", D("0")) == D("1.27")  # zero/negativo = usa o típico


def test_densidade_invalida() -> None:
    with pytest.raises(ValueError, match="positiva"):
        convert_grams(D("10"), D("0"), D("1"))
