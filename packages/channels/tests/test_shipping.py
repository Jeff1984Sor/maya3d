import json
from decimal import Decimal
from typing import Any

import httpx
import pytest

from print3d_channels.shipping import MelhorEnvio, ShippingError, parcel_from_mm


def _client(status: int, payload: Any, seen: list[dict[str, Any]]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(
            {
                "url": str(request.url),
                "headers": dict(request.headers),
                "json": json.loads(request.content),
            }
        )
        return httpx.Response(status, json=payload)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


RESPONSE = [
    {
        "id": 1,
        "name": "PAC",
        "price": "25.10",
        "custom_price": "22.40",
        "delivery_time": 8,
        "custom_delivery_time": 9,
        "company": {"name": "Correios"},
    },
    {
        "id": 2,
        "name": "SEDEX",
        "price": "41.00",
        "custom_price": "38.90",
        "delivery_time": 3,
        "custom_delivery_time": 4,
        "company": {"name": "Correios"},
    },
    {"id": 3, "name": ".Package", "error": "Transportadora não atende este trecho."},
]


def test_caixa_em_cm_com_minimos() -> None:
    p = parcel_from_mm("v1", (95, 12, 101), 180, Decimal("30"), 2)
    assert (p.width_cm, p.height_cm, p.length_cm) == (11, 2, 16)
    assert p.weight_kg == 0.18
    assert p.quantity == 2


async def test_cotacao() -> None:
    seen: list[dict[str, Any]] = []
    me = MelhorEnvio(
        "tok", env="sandbox", contact_email="ti@loja.com", client=_client(200, RESPONSE, seen)
    )
    parcel = parcel_from_mm("v1", (150, 100, 60), 300, Decimal("49.90"), 1)
    rates = await me.quote("18000000", "01310100", [parcel])
    assert [r.service for r in rates] == ["PAC", "SEDEX"]  # erro ignorado, ordem por preço
    assert rates[0].price == Decimal("22.40")  # preço com o desconto da conta
    assert rates[0].days == 9
    req = seen[0]
    assert req["url"] == "https://sandbox.melhorenvio.com.br/api/v2/me/shipment/calculate"
    assert req["headers"]["authorization"] == "Bearer tok"
    assert req["headers"]["user-agent"] == "Print3D (ti@loja.com)"
    assert req["json"]["products"][0] == {
        "id": "v1",
        "width": 15,
        "height": 10,
        "length": 16,
        "weight": 0.3,
        "insurance_value": 49.9,
        "quantity": 1,
    }


async def test_token_recusado() -> None:
    me = MelhorEnvio("x", env="producao", contact_email="a@b.c", client=_client(401, {}, []))
    with pytest.raises(ShippingError, match="token"):
        await me.quote("1", "2", [parcel_from_mm("v", (10, 10, 10), 10, Decimal(1), 1)])


def test_ambiente_invalido() -> None:
    with pytest.raises(ShippingError):
        MelhorEnvio("x", env="teste", contact_email="a@b.c")
