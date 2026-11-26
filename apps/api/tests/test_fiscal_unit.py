from decimal import Decimal

import pytest

from print3d_api.services.fiscal import FiscalError, parse_aliquotas


def test_aliquotas_internas_do_difal() -> None:
    tabela = parse_aliquotas("MG=18; rj=20+2;PR=19,5\nBA=20.5")
    assert tabela["MG"].aliquota_interna == Decimal(18)
    assert tabela["RJ"].aliquota_fcp == Decimal(2)
    assert tabela["PR"].aliquota_interna == Decimal("19.5")
    assert tabela["BA"].aliquota_interna == Decimal("20.5")
    assert parse_aliquotas("") == {}
    with pytest.raises(FiscalError):
        parse_aliquotas("MG=dezoito")


def test_cpf_no_checkout() -> None:
    from pydantic import ValidationError

    from print3d_api.schemas.store import CheckoutIn, cpf_valido

    assert cpf_valido("52998224725")
    assert not cpf_valido("52998224724")
    assert not cpf_valido("11111111111")
    base = {
        "cart_token": "t",
        "name": "Maria",
        "email": "maria@gmail.com",
        "whatsapp": "11999999999",
        "accept_terms": True,
        "cep": "18081000",
        "street": "Rua A",
        "number": "1",
        "shipping_option": "local",
    }
    assert CheckoutIn(**base, cpf="529.982.247-25").cpf == "52998224725"
    assert CheckoutIn(**base, cpf="").cpf is None
    with pytest.raises(ValidationError, match="CPF inválido"):
        CheckoutIn(**base, cpf="123.456.789-00")
