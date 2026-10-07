"""Mercado Pago (gateway de pagamento). Pix pela API de pagamentos; cartão entra com o
domínio (o formulário seguro do Mercado Pago exige HTTPS).

Documentação oficial:
- POST https://api.mercadopago.com/v1/payments  (Bearer access token, X-Idempotency-Key)
  payment_method_id = "pix" → point_of_interaction.transaction_data.{qr_code, qr_code_base64,
  ticket_url}
- GET /v1/payments/{id} → status (approved, pending, cancelled, rejected...)
- Aviso (webhook): cabeçalho x-signature "ts=...,v1=..." = HMAC-SHA256(segredo,
  "id:{data.id em minúsculas};request-id:{x-request-id};ts:{ts};")
"""

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx

API = "https://api.mercadopago.com"


class MercadoPagoError(Exception):
    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class PixCharge:
    payment_id: str
    status: str
    qr_code: str  # "copia e cola"
    qr_code_base64: str  # imagem PNG em base64
    ticket_url: str | None
    expires_at: datetime


@dataclass(frozen=True)
class PaymentState:
    payment_id: str
    status: str  # approved | pending | in_process | rejected | cancelled | refunded ...
    amount: Decimal
    external_reference: str | None
    fee: Decimal = Decimal(0)  # taxa cobrada pelo Mercado Pago (fee_details do pagamento)

    @property
    def paid(self) -> bool:
        return self.status == "approved"


def verify_signature(
    secret: str, x_signature: str | None, x_request_id: str | None, data_id: str
) -> bool:
    if not x_signature or not data_id:
        return False
    parts = dict(p.strip().split("=", 1) for p in x_signature.split(",") if "=" in p)
    ts, v1 = parts.get("ts"), parts.get("v1")
    if not ts or not v1:
        return False
    manifest = f"id:{data_id.lower()};"
    if x_request_id:
        manifest += f"request-id:{x_request_id};"
    manifest += f"ts:{ts};"
    expected = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


class MercadoPago:
    def __init__(self, access_token: str, *, client: httpx.AsyncClient | None = None) -> None:
        self._token = access_token
        self._client = client

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/json",
            **kwargs.pop("headers", {}),
        }
        client = self._client or httpx.AsyncClient(timeout=20)
        try:
            res = await client.request(method, f"{API}{path}", headers=headers, **kwargs)
        except httpx.HTTPError as exc:
            raise MercadoPagoError(f"Mercado Pago fora do ar: {type(exc).__name__}") from exc
        finally:
            if self._client is None:
                await client.aclose()
        data: dict[str, Any] = res.json() if res.content else {}
        if res.status_code >= 400:
            if res.status_code in (401, 403):
                raise MercadoPagoError(
                    "credencial do Mercado Pago recusada (confira em Integrações)", res.status_code
                )
            raise MercadoPagoError(
                str(data.get("message") or f"Mercado Pago respondeu {res.status_code}"),
                res.status_code,
            )
        return data

    async def create_pix(
        self,
        *,
        amount: Decimal,
        description: str,
        payer_email: str,
        payer_name: str,
        reference: str,
        idempotency_key: str,
        expires_in: timedelta = timedelta(hours=24),
        notification_url: str | None = None,
    ) -> PixCharge:
        expires_at = datetime.now(UTC) + expires_in
        first, _, last = payer_name.strip().partition(" ")
        body: dict[str, Any] = {
            "transaction_amount": float(amount.quantize(Decimal("0.01"))),
            "description": description[:250],
            "payment_method_id": "pix",
            "external_reference": reference,
            "date_of_expiration": expires_at.isoformat(timespec="milliseconds"),
            "payer": {"email": payer_email, "first_name": first, "last_name": last or first},
        }
        if notification_url:
            body["notification_url"] = notification_url
        data = await self._request(
            "POST", "/v1/payments", json=body, headers={"X-Idempotency-Key": idempotency_key}
        )
        tx = (data.get("point_of_interaction") or {}).get("transaction_data") or {}
        if not tx.get("qr_code"):
            raise MercadoPagoError("o Mercado Pago não devolveu o QR Code do Pix")
        return PixCharge(
            payment_id=str(data["id"]),
            status=str(data.get("status", "pending")),
            qr_code=str(tx["qr_code"]),
            qr_code_base64=str(tx.get("qr_code_base64", "")),
            ticket_url=tx.get("ticket_url"),
            expires_at=expires_at,
        )

    async def payment(self, payment_id: str) -> PaymentState:
        if not payment_id.isdigit():
            raise MercadoPagoError("id de pagamento inválido")
        data = await self._request("GET", f"/v1/payments/{payment_id}")
        return PaymentState(
            payment_id=str(data.get("id", payment_id)),
            status=str(data.get("status", "")),
            amount=Decimal(str(data.get("transaction_amount", 0))),
            external_reference=data.get("external_reference"),
            fee=sum(
                (
                    Decimal(str(f.get("amount", 0)))
                    for f in data.get("fee_details") or []
                    if f.get("type") == "mercadopago_fee"
                ),
                Decimal(0),
            ),
        )
