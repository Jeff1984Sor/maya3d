"""Bloco padrão da descrição do anúncio: medidas reais, material, prazo e cuidados."""

from print3d_api.models import Variant
from print3d_api.services.mercadolivre import details_block


def test_medidas_em_cm_com_altura_largura_profundidade() -> None:
    text = details_block(Variant(dims_mm=[80.0, 25.6, 120.0]), 5)
    assert "- Altura: 12 cm" in text
    assert "- Largura: 8 cm" in text
    assert "- Profundidade: 2,6 cm" in text
    assert "até 5 dias úteis" in text


def test_sem_medidas_e_pronta_entrega() -> None:
    text = details_block(Variant(dims_mm=None), None)
    assert "MEDIDAS" not in text
    assert "pronta entrega" in text


def test_sem_emoji_porque_o_ml_so_aceita_texto_simples() -> None:
    text = details_block(Variant(dims_mm=[80.0, 25.6, 120.0]), 5)
    assert all(ord(ch) < 0x2000 for ch in text)
