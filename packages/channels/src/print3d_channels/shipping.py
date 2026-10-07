"""Cotação de frete. Contrato `ShippingQuoter` + Melhor Envio (API v2, cálculo por produtos).

Documentação oficial: POST {base}/api/v2/me/shipment/calculate, Bearer token, User-Agent
"Aplicação (email de contato técnico)". Medidas em centímetros, peso em kg.
"""

import logging
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

import httpx

log = logging.getLogger("print3d.shipping")
BASE_URL = {
    "producao": "https://melhorenvio.com.br",
    "sandbox": "https://sandbox.melhorenvio.com.br",
}
# Mínimos aceitos pelos Correios para caixa (cm)
MIN_CM = (11, 2, 16)  # largura, altura, comprimento


class ShippingError(Exception):
    pass


@dataclass(frozen=True)
class Parcel:
    """Uma unidade embalada (o provedor junta várias em volumes)."""

    ref: str
    width_cm: int
    height_cm: int
    length_cm: int
    weight_kg: float
    value: Decimal
    quantity: int = 1


@dataclass(frozen=True)
class ShippingRate:
    service_id: str
    carrier: str
    service: str
    price: Decimal
    days: int | None


class ShippingQuoter(Protocol):
    async def quote(
        self, origin_cep: str, dest_cep: str, parcels: list[Parcel]
    ) -> list[ShippingRate]: ...


def parcel_from_mm(
    ref: str, dims_mm: tuple[float, float, float], weight_g: float, value: Decimal, qty: int
) -> Parcel:
    """Caixa em mm → cm inteiros (arredonda para cima), respeitando os mínimos."""
    w, h, length = (math.ceil(d / 10) for d in dims_mm)
    return Parcel(
        ref=ref,
        width_cm=max(w, MIN_CM[0]),
        height_cm=max(h, MIN_CM[1]),
        length_cm=max(length, MIN_CM[2]),
        weight_kg=max(round(weight_g / 1000, 3), 0.05),
        value=value,
        quantity=qty,
    )


class MelhorEnvio:
    def __init__(
        self,
        token: str,
        *,
        env: str,
        contact_email: str,
        services: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if env not in BASE_URL:
            raise ShippingError("ambiente do Melhor Envio: producao ou sandbox")
        self._token = token
        self._url = f"{BASE_URL[env]}/api/v2/me/shipment/calculate"
        self._agent = f"Print3D ({contact_email})"
        self._services = services
        self._client = client

    def _body(self, origin: str, dest: str, parcels: list[Parcel]) -> dict[str, Any]:
        body: dict[str, Any] = {
            "from": {"postal_code": origin},
            "to": {"postal_code": dest},
            "products": [
                {
                    "id": p.ref,
                    "width": p.width_cm,
                    "height": p.height_cm,
                    "length": p.length_cm,
                    "weight": p.weight_kg,
                    "insurance_value": float(p.value),
                    "quantity": p.quantity,
                }
                for p in parcels
            ],
            "options": {"receipt": False, "own_hand": False},
        }
        if self._services:
            body["services"] = self._services
        return body

    async def quote(
        self, origin_cep: str, dest_cep: str, parcels: list[Parcel]
    ) -> list[ShippingRate]:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": self._agent,
        }
        client = self._client or httpx.AsyncClient(timeout=12)
        try:
            res = await client.post(
                self._url, json=self._body(origin_cep, dest_cep, parcels), headers=headers
            )
        except httpx.HTTPError as exc:
            raise ShippingError(f"Melhor Envio fora do ar: {type(exc).__name__}") from exc
        finally:
            if self._client is None:
                await client.aclose()
        if res.status_code in (401, 403):
            raise ShippingError("token do Melhor Envio recusado (confira em Integrações)")
        if res.status_code >= 400:
            raise ShippingError(f"Melhor Envio respondeu {res.status_code}")
        data = res.json()
        rates: list[ShippingRate] = []
        for item in data if isinstance(data, list) else []:
            if item.get("error") or not (item.get("custom_price") or item.get("price")):
                continue  # serviço indisponível para este trecho/medida
            rates.append(
                ShippingRate(
                    service_id=str(item["id"]),
                    carrier=str((item.get("company") or {}).get("name", "")),
                    service=str(item.get("name", "")),
                    price=Decimal(str(item.get("custom_price") or item["price"])).quantize(
                        Decimal("0.01")
                    ),
                    days=item.get("custom_delivery_time") or item.get("delivery_time"),
                )
            )
        return sorted(rates, key=lambda r: r.price)
