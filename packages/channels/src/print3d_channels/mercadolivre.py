"""Mercado Livre (Brasil, site MLB): OAuth 2.0 com PKCE, categoria, tarifa real, anúncio,
pedidos e perguntas.

Contrato público da API (developers.mercadolivre.com.br):
- autorização: https://auth.mercadolivre.com.br/authorization?response_type=code&client_id=
  &redirect_uri=&state=&code_challenge=&code_challenge_method=S256
- token: POST https://api.mercadolibre.com/oauth/token (form) grant_type=authorization_code |
  refresh_token. O refresh token é de uso único: guarde sempre o novo.
- tarifa: GET /sites/MLB/listing_prices?price=&listing_type_id=&category_id= (nunca no código)

Tokens são do vendedor: quem guarda (cifrado) é a API; este cliente só fala HTTP.
"""

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import httpx

AUTH_URL = "https://auth.mercadolivre.com.br/authorization"
API = "https://api.mercadolibre.com"
SITE = "MLB"


class MercadoLivreError(Exception):
    def __init__(self, message: str, status: int = 0, cause: list[str] | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.cause = cause or []


@dataclass(frozen=True)
class Tokens:
    access_token: str
    refresh_token: str
    expires_at: datetime
    user_id: str


@dataclass(frozen=True)
class Category:
    id: str
    name: str
    domain: str | None


@dataclass(frozen=True)
class ListingFee:
    listing_type: str
    sale_fee: Decimal  # valor total da tarifa para o preço consultado
    percentage: Decimal | None
    fixed: Decimal | None


def pkce_pair() -> tuple[str, str]:
    """(verifier, challenge S256)."""
    verifier = secrets.token_urlsafe(64)[:96]
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).decode().rstrip("=")


def authorization_url(client_id: str, redirect_uri: str, state: str, challenge: str) -> str:
    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTH_URL}?{urlencode(query)}"


def _causes(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return []
    out = [
        str(c.get("message") or c.get("code"))
        for c in data.get("cause") or []
        if isinstance(c, dict)
    ]
    return [c for c in out if c and c != "None"]


class MercadoLivre:
    def __init__(
        self, client_id: str, client_secret: str, *, client: httpx.AsyncClient | None = None
    ) -> None:
        self._id = client_id
        self._secret = client_secret
        self._client = client

    async def _request(
        self, method: str, path: str, *, token: str | None = None, **kwargs: Any
    ) -> Any:
        headers = {"Accept": "application/json", **kwargs.pop("headers", {})}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        client = self._client or httpx.AsyncClient(timeout=20)
        try:
            res = await client.request(method, f"{API}{path}", headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise MercadoLivreError(f"Mercado Livre fora do ar: {type(exc).__name__}") from exc
        finally:
            if self._client is None:
                await client.aclose()
        data = res.json() if res.content else {}
        if res.status_code >= 400:
            message = data.get("message") if isinstance(data, dict) else None
            raise MercadoLivreError(
                str(message or f"Mercado Livre respondeu {res.status_code}"),
                res.status_code,
                _causes(data),
            )
        return data

    # --- OAuth -------------------------------------------------------------------------------
    async def _token(self, form: dict[str, str]) -> Tokens:
        data = await self._request(
            "POST",
            "/oauth/token",
            data={**form, "client_id": self._id, "client_secret": self._secret},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        return Tokens(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=datetime.now(UTC) + timedelta(seconds=int(data.get("expires_in", 21600))),
            user_id=str(data.get("user_id", "")),
        )

    async def exchange_code(self, code: str, redirect_uri: str, verifier: str) -> Tokens:
        return await self._token(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": verifier,
            }
        )

    async def refresh(self, refresh_token: str) -> Tokens:
        return await self._token({"grant_type": "refresh_token", "refresh_token": refresh_token})

    async def me(self, token: str) -> dict[str, Any]:
        data: dict[str, Any] = await self._request("GET", "/users/me", token=token)
        return data

    async def is_user_products_seller(self, token: str) -> bool:
        """Conta migrada para User Products publica com ``family_name`` (sem ``title``)."""
        return "user_product_seller" in ((await self.me(token)).get("tags") or [])

    # --- Catálogo e tarifa -------------------------------------------------------------------
    async def predict_category(self, token: str, title: str) -> Category | None:
        data = await self._request(
            "GET",
            f"/sites/{SITE}/domain_discovery/search",
            token=token,
            params={"q": title, "limit": 1},
        )
        if not data:
            return None
        first = data[0]
        return Category(
            first["category_id"], first.get("category_name", ""), first.get("domain_id")
        )

    async def required_attributes(self, token: str, category_id: str) -> list[dict[str, Any]]:
        data = await self._request("GET", f"/categories/{category_id}/attributes", token=token)
        return [
            a
            for a in data
            if (a.get("tags") or {}).get("required")
            or (a.get("tags") or {}).get("catalog_required")
        ]

    async def listing_fee(
        self, token: str, *, price: Decimal, category_id: str, listing_type: str
    ) -> ListingFee:
        data = await self._request(
            "GET",
            f"/sites/{SITE}/listing_prices",
            token=token,
            params={
                "price": str(price),
                "category_id": category_id,
                "listing_type_id": listing_type,
            },
        )
        row = data[0] if isinstance(data, list) else data
        details = row.get("sale_fee_details") or {}
        return ListingFee(
            listing_type=row.get("listing_type_id", listing_type),
            sale_fee=Decimal(str(row.get("sale_fee_amount", 0))),
            percentage=Decimal(str(details["percentage_fee"]))
            if "percentage_fee" in details
            else None,
            fixed=Decimal(str(details["fixed_fee"])) if "fixed_fee" in details else None,
        )

    # --- Anúncios ----------------------------------------------------------------------------
    async def create_item(self, token: str, item: dict[str, Any]) -> dict[str, Any]:
        data: dict[str, Any] = await self._request("POST", "/items", token=token, json=item)
        return data

    async def set_description(self, token: str, item_id: str, text: str) -> None:
        await self._request(
            "POST", f"/items/{item_id}/description", token=token, json={"plain_text": text}
        )

    async def update_item(
        self, token: str, item_id: str, changes: dict[str, Any]
    ) -> dict[str, Any]:
        data: dict[str, Any] = await self._request(
            "PUT", f"/items/{item_id}", token=token, json=changes
        )
        return data

    # --- Pedidos e perguntas (chegam por notificação) ----------------------------------------
    async def get(self, token: str, resource: str) -> dict[str, Any]:
        """Lê o recurso avisado pela notificação (ex.: /orders/123, /questions/456)."""
        if not resource.startswith("/") or ".." in resource:
            raise MercadoLivreError("recurso inválido")
        data: dict[str, Any] = await self._request("GET", resource, token=token)
        return data

    async def answer(self, token: str, question_id: int, text: str) -> None:
        await self._request(
            "POST", "/answers", token=token, json={"question_id": question_id, "text": text}
        )


def item_payload(
    *,
    title: str,
    category_id: str,
    price: Decimal,
    quantity: int,
    listing_type: str,
    pictures: list[str],
    attributes: list[dict[str, Any]],
    user_products: bool = False,
    manufacturing_days: int | None = None,
) -> dict[str, Any]:
    """Corpo de POST /items. Fotos precisam ser URLs públicas (HTTPS, com domínio).

    Conta no modelo User Products (tag ``user_product_seller``): manda ``family_name`` e não
    manda ``title`` — o ML gera o título a partir dele e dos atributos.
    """
    name = {"family_name": title[:60]} if user_products else {"title": title[:60]}
    terms = (
        {"sale_terms": [{"id": "MANUFACTURING_TIME", "value_name": f"{manufacturing_days} dias"}]}
        if manufacturing_days
        else {}
    )
    return {
        "site_id": SITE,
        **name,
        **terms,
        "category_id": category_id,
        "price": float(price),
        "currency_id": "BRL",
        "available_quantity": quantity,
        "buying_mode": "buy_it_now",
        "condition": "new",
        "listing_type_id": listing_type,
        "pictures": [{"source": url} for url in pictures[:10]],
        "attributes": attributes,
    }
