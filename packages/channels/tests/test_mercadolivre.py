import base64
import hashlib
import json
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from print3d_channels.mercadolivre import (
    MercadoLivre,
    MercadoLivreError,
    authorization_url,
    item_payload,
    pkce_pair,
)


def _client(
    routes: dict[tuple[str, str], tuple[int, Any]], seen: list[httpx.Request]
) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        status, body = routes[(request.method, request.url.path)]
        return httpx.Response(status, json=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_pkce_e_url_de_autorizacao() -> None:
    verifier, challenge = pkce_pair()
    expected = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    )
    assert challenge == expected
    url = urlparse(authorization_url("123", "https://loja.com/cb", "st", challenge))
    q = parse_qs(url.query)
    assert url.netloc == "auth.mercadolivre.com.br"
    assert q["response_type"] == ["code"]
    assert q["code_challenge_method"] == ["S256"]
    assert q["state"] == ["st"]


async def test_troca_codigo_e_renova() -> None:
    seen: list[httpx.Request] = []
    token = {"access_token": "A", "refresh_token": "R2", "expires_in": 21600, "user_id": 99}
    ml = MercadoLivre("id", "seg", client=_client({("POST", "/oauth/token"): (200, token)}, seen))
    tokens = await ml.exchange_code("CODE", "https://loja.com/cb", "VER")
    assert (tokens.access_token, tokens.refresh_token, tokens.user_id) == ("A", "R2", "99")
    form = parse_qs(seen[0].content.decode())
    assert form["grant_type"] == ["authorization_code"]
    assert form["code_verifier"] == ["VER"]
    assert form["client_secret"] == ["seg"]
    await ml.refresh("R1")
    assert parse_qs(seen[1].content.decode())["refresh_token"] == ["R1"]


async def test_categoria_tarifa_e_erros() -> None:
    seen: list[httpx.Request] = []
    routes = {
        ("GET", "/sites/MLB/domain_discovery/search"): (
            200,
            [
                {
                    "category_id": "MLB1234",
                    "category_name": "Chaveiros",
                    "domain_id": "MLB-KEYCHAINS",
                }
            ],
        ),
        ("GET", "/sites/MLB/listing_prices"): (
            200,
            {
                "listing_type_id": "gold_special",
                "sale_fee_amount": 6.5,
                "sale_fee_details": {"percentage_fee": 11.5, "fixed_fee": 0},
            },
        ),
        ("POST", "/items"): (
            400,
            {
                "message": "Validation error",
                "cause": [
                    {"code": "item.attribute.missing_required", "message": "BRAND obrigatório"}
                ],
            },
        ),
    }
    ml = MercadoLivre("id", "seg", client=_client(routes, seen))
    cat = await ml.predict_category("T", "Chaveiro com nome")
    assert cat is not None
    assert cat.id == "MLB1234"
    fee = await ml.listing_fee(
        "T", price=Decimal("39.90"), category_id="MLB1234", listing_type="gold_special"
    )
    assert fee.sale_fee == Decimal("6.5")
    assert fee.percentage == Decimal("11.5")
    assert seen[1].headers["authorization"] == "Bearer T"
    with pytest.raises(MercadoLivreError) as err:
        await ml.create_item("T", {})
    assert err.value.cause == ["BRAND obrigatório"]


async def test_recurso_da_notificacao_e_seguro() -> None:
    ml = MercadoLivre("id", "seg", client=_client({}, []))
    with pytest.raises(MercadoLivreError):
        await ml.get("T", "https://outro.com/x")


def test_corpo_do_anuncio() -> None:
    body = item_payload(
        title="Chaveiro personalizado com nome em impressão 3D cores à escolha com argola",
        category_id="MLB1",
        price=Decimal("29.90"),
        quantity=50,
        listing_type="gold_special",
        pictures=["https://loja.com/m/a.webp"],
        attributes=[{"id": "BRAND", "value_name": "Genérica"}],
    )
    assert len(body["title"]) == 60
    assert "family_name" not in body
    assert body["currency_id"] == "BRL"
    assert body["pictures"] == [{"source": "https://loja.com/m/a.webp"}]
    assert json.dumps(body)  # serializável


def test_item_payload_user_products_usa_family_name_sem_title() -> None:
    body = item_payload(
        title="Crucifixo de parede em impressão 3D",
        category_id="MLB1",
        price=Decimal("19.90"),
        quantity=50,
        listing_type="gold_special",
        pictures=["https://loja.com/m/a.webp"],
        attributes=[],
        user_products=True,
    )
    assert body["family_name"] == "Crucifixo de parede em impressão 3D"
    assert "title" not in body
