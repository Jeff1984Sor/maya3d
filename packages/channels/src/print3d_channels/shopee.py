"""Shopee Open Platform (API v2): autorização da loja, tokens, categoria, foto, anúncio,
pedidos e verificação do push (webhook).

Assinatura (documentação oficial): sign = hex(HMAC-SHA256(partner_key, base)), com
- APIs públicas: base = partner_id + path + timestamp
- APIs da loja:  base = partner_id + path + timestamp + access_token + shop_id
O host varia por ambiente/região: configurável (padrão: produção global).
Comissão da Shopee não vem por API simples: fica na tabela de tarifas (nunca no código).
"""

import hashlib
import hmac
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import httpx

DEFAULT_HOST = "https://partner.shopeemobile.com"
SANDBOX_HOST = "https://partner.test-stable.shopeemobile.com"
PAID_STATUSES = frozenset(
    {"READY_TO_SHIP", "PROCESSED", "SHIPPED", "TO_CONFIRM_RECEIVE", "COMPLETED"}
)


class ShopeeError(Exception):
    def __init__(self, message: str, code: str = "") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ShopTokens:
    access_token: str
    refresh_token: str
    expires_at: datetime
    shop_id: str


def sign(partner_key: str, *parts: str | int) -> str:
    base = "".join(str(p) for p in parts)
    return hmac.new(partner_key.encode(), base.encode(), hashlib.sha256).hexdigest()


def verify_push(partner_key: str, url: str, raw_body: bytes, authorization: str | None) -> bool:
    """Push da Shopee: Authorization = hex(HMAC-SHA256(partner_key, url + '|' + corpo))."""
    if not authorization:
        return False
    expected = hmac.new(
        partner_key.encode(), url.encode() + b"|" + raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, authorization)


class Shopee:
    def __init__(
        self,
        partner_id: int,
        partner_key: str,
        *,
        host: str = DEFAULT_HOST,
        client: httpx.AsyncClient | None = None,
        clock: Any = time.time,
    ) -> None:
        self._pid = partner_id
        self._key = partner_key
        self._host = host.rstrip("/")
        self._client = client
        self._clock = clock

    def _query(
        self, path: str, token: str | None = None, shop_id: str | None = None
    ) -> dict[str, Any]:
        ts = int(self._clock())
        parts: list[str | int] = [self._pid, path, ts]
        query: dict[str, Any] = {"partner_id": self._pid, "timestamp": ts}
        if token and shop_id:
            parts += [token, shop_id]
            query.update(access_token=token, shop_id=int(shop_id))
        query["sign"] = sign(self._key, *parts)
        return query

    async def _call(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        shop_id: str | None = None,
        params: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        query = {**self._query(path, token, shop_id), **(params or {})}
        client = self._client or httpx.AsyncClient(timeout=25)
        try:
            res = await client.request(method, f"{self._host}{path}", params=query, **kwargs)
        except httpx.HTTPError as exc:
            raise ShopeeError(f"Shopee fora do ar: {type(exc).__name__}") from exc
        finally:
            if self._client is None:
                await client.aclose()
        data: dict[str, Any] = res.json() if res.content else {}
        if res.status_code >= 400 or data.get("error"):
            raise ShopeeError(
                str(
                    data.get("message")
                    or data.get("error")
                    or f"Shopee respondeu {res.status_code}"
                ),
                str(data.get("error", "")),
            )
        return data

    # --- Autorização -------------------------------------------------------------------------
    def authorization_url(self, redirect: str) -> str:
        path = "/api/v2/shop/auth_partner"
        return f"{self._host}{path}?{urlencode({**self._query(path), 'redirect': redirect})}"

    def _tokens(self, data: dict[str, Any], shop_id: str) -> ShopTokens:
        return ShopTokens(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=datetime.now(UTC) + timedelta(seconds=int(data.get("expire_in", 14400))),
            shop_id=shop_id,
        )

    async def exchange_code(self, code: str, shop_id: str) -> ShopTokens:
        data = await self._call(
            "POST",
            "/api/v2/auth/token/get",
            json={"code": code, "shop_id": int(shop_id), "partner_id": self._pid},
        )
        return self._tokens(data, shop_id)

    async def refresh(self, refresh_token: str, shop_id: str) -> ShopTokens:
        data = await self._call(
            "POST",
            "/api/v2/auth/access_token/get",
            json={"refresh_token": refresh_token, "shop_id": int(shop_id), "partner_id": self._pid},
        )
        return self._tokens(data, shop_id)

    async def shop_info(self, token: str, shop_id: str) -> dict[str, Any]:
        return await self._call("GET", "/api/v2/shop/get_shop_info", token=token, shop_id=shop_id)

    # --- Anúncio -----------------------------------------------------------------------------
    async def recommend_category(self, token: str, shop_id: str, name: str) -> int | None:
        data = await self._call(
            "GET",
            "/api/v2/product/category_recommend",
            token=token,
            shop_id=shop_id,
            params={"item_name": name},
        )
        ids = (data.get("response") or {}).get("category_id") or []
        return int(ids[0]) if ids else None

    async def upload_image(self, image: bytes, filename: str = "foto.jpg") -> str:
        data = await self._call(
            "POST", "/api/v2/media_space/upload_image", files={"image": (filename, image)}
        )
        info = (data.get("response") or {}).get("image_info") or {}
        if not info.get("image_id"):
            raise ShopeeError("a Shopee não devolveu o id da imagem")
        return str(info["image_id"])

    async def logistics(self, token: str, shop_id: str) -> list[int]:
        data = await self._call(
            "GET", "/api/v2/logistics/get_channel_list", token=token, shop_id=shop_id
        )
        channels = (data.get("response") or {}).get("logistics_channel_list") or []
        return [int(c["logistics_channel_id"]) for c in channels if c.get("enabled")]

    async def add_item(self, token: str, shop_id: str, item: dict[str, Any]) -> str:
        data = await self._call(
            "POST", "/api/v2/product/add_item", token=token, shop_id=shop_id, json=item
        )
        return str((data.get("response") or {}).get("item_id"))

    # --- Pedidos -----------------------------------------------------------------------------
    async def order_detail(self, token: str, shop_id: str, order_sn: str) -> dict[str, Any]:
        data = await self._call(
            "GET",
            "/api/v2/order/get_order_detail",
            token=token,
            shop_id=shop_id,
            params={
                "order_sn_list": order_sn,
                "response_optional_fields": "item_list,total_amount",
            },
        )
        orders = (data.get("response") or {}).get("order_list") or []
        if not orders:
            raise ShopeeError(f"pedido {order_sn} não encontrado")
        order: dict[str, Any] = orders[0]
        return order


def item_payload(
    *,
    name: str,
    description: str,
    price: Decimal,
    stock: int,
    category_id: int,
    image_ids: list[str],
    weight_kg: float,
    dims_cm: tuple[int, int, int],
    logistic_ids: list[int],
) -> dict[str, Any]:
    length, width, height = dims_cm
    return {
        "item_name": name[:120],
        "description": description[:3000],
        "original_price": float(price),
        "seller_stock": [{"stock": stock}],
        "category_id": category_id,
        "image": {"image_id_list": image_ids[:9]},
        "weight": round(weight_kg, 3),
        "dimension": {"package_length": length, "package_width": width, "package_height": height},
        "logistic_info": [{"logistic_id": i, "enabled": True} for i in logistic_ids],
        "condition": "NEW",
        "item_status": "NORMAL",
        "brand": {"brand_id": 0, "original_brand_name": "NoBrand"},
    }
