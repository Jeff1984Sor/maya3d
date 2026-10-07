import hashlib
import hmac
import json
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from print3d_channels.shopee import Shopee, ShopeeError, item_payload, sign, verify_push


def _client(routes: dict[str, Any], seen: list[httpx.Request]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        status, body = routes[request.url.path]
        return httpx.Response(status, json=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _shopee(routes: dict[str, Any], seen: list[httpx.Request]) -> Shopee:
    return Shopee(1001, "chave", client=_client(routes, seen), clock=lambda: 1700000000)


def test_assinatura_publica_e_da_loja() -> None:
    expected = hmac.new(
        b"chave", b"1001/api/v2/shop/auth_partner1700000000", hashlib.sha256
    ).hexdigest()
    assert sign("chave", 1001, "/api/v2/shop/auth_partner", 1700000000) == expected
    url = _shopee({}, []).authorization_url("https://api.loja.test/cb")
    q = parse_qs(urlparse(url).query)
    assert q["sign"] == [expected]
    assert q["redirect"] == ["https://api.loja.test/cb"]


async def test_chamada_da_loja_assina_com_token_e_loja() -> None:
    seen: list[httpx.Request] = []
    sh = _shopee(
        {"/api/v2/product/category_recommend": (200, {"response": {"category_id": [100]}})}, seen
    )
    assert await sh.recommend_category("TOK", "55", "Chaveiro") == 100
    q = parse_qs(seen[0].url.query.decode())
    base = "1001/api/v2/product/category_recommend1700000000TOK55"
    assert q["sign"] == [hmac.new(b"chave", base.encode(), hashlib.sha256).hexdigest()]
    assert q["access_token"] == ["TOK"]
    assert q["shop_id"] == ["55"]


async def test_tokens_e_erros() -> None:
    seen: list[httpx.Request] = []
    sh = _shopee(
        {
            "/api/v2/auth/token/get": (
                200,
                {"access_token": "A", "refresh_token": "R", "expire_in": 14400},
            ),
            "/api/v2/product/add_item": (
                200,
                {"error": "product.error_param", "message": "categoria inválida"},
            ),
        },
        seen,
    )
    tokens = await sh.exchange_code("CODE", "55")
    assert (tokens.access_token, tokens.shop_id) == ("A", "55")
    assert json.loads(seen[0].content) == {"code": "CODE", "shop_id": 55, "partner_id": 1001}
    with pytest.raises(ShopeeError, match="categoria inválida"):
        await sh.add_item("A", "55", {})


def test_push_assinado() -> None:
    body = b'{"code":3,"shop_id":55}'
    url = "https://api.loja.test/v1/webhooks/shopee"
    good = hmac.new(b"chave", url.encode() + b"|" + body, hashlib.sha256).hexdigest()
    assert verify_push("chave", url, body, good)
    assert not verify_push("chave", url, body + b" ", good)
    assert not verify_push("chave", url, body, None)


def test_corpo_do_anuncio() -> None:
    body = item_payload(
        name="Chaveiro personalizado",
        description="Feito em impressão 3D",
        price=Decimal("29.90"),
        stock=50,
        category_id=100,
        image_ids=["img1"],
        weight_kg=0.08,
        dims_cm=(16, 11, 2),
        logistic_ids=[90001],
    )
    assert body["seller_stock"] == [{"stock": 50}]
    assert body["dimension"]["package_length"] == 16
    assert body["logistic_info"] == [{"logistic_id": 90001, "enabled": True}]
