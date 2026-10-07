import hashlib
import hmac
import json
from decimal import Decimal
from typing import Any

import httpx
import pytest

from print3d_channels.mercadopago import MercadoPago, MercadoPagoError, verify_signature


def _client(status: int, body: Any, seen: list[httpx.Request]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json=body)

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


PIX = {
    "id": 123456,
    "status": "pending",
    "point_of_interaction": {
        "type": "PIX",
        "transaction_data": {
            "qr_code": "00020126...",
            "qr_code_base64": "iVBORw0KGgo=",
            "ticket_url": "https://mp/t",
        },
    },
}


async def test_cria_pix_com_idempotencia() -> None:
    seen: list[httpx.Request] = []
    mp = MercadoPago("TEST-token", client=_client(201, PIX, seen))
    charge = await mp.create_pix(
        amount=Decimal("59.9"),
        description="Pedido #1001",
        payer_email="ana@example.com",
        payer_name="Ana Souza",
        reference="pedido-1001",
        idempotency_key="tok-1001",
    )
    assert charge.payment_id == "123456"
    assert charge.qr_code == "00020126..."
    req = seen[0]
    assert str(req.url) == "https://api.mercadopago.com/v1/payments"
    assert req.headers["x-idempotency-key"] == "tok-1001"
    assert req.headers["authorization"] == "Bearer TEST-token"
    body = json.loads(req.content)
    assert body["payment_method_id"] == "pix"
    assert body["transaction_amount"] == 59.9
    assert body["payer"] == {"email": "ana@example.com", "first_name": "Ana", "last_name": "Souza"}
    assert "notification_url" not in body  # sem domínio: confirmação por consulta


async def test_consulta_e_erros() -> None:
    mp = MercadoPago(
        "t", client=_client(200, {"id": 9, "status": "approved", "transaction_amount": 10}, [])
    )
    state = await mp.payment("9")
    assert state.paid
    with pytest.raises(MercadoPagoError):
        await mp.payment("../x")
    bad = MercadoPago("t", client=_client(401, {"message": "invalid"}, []))
    with pytest.raises(MercadoPagoError, match="credencial"):
        await bad.payment("1")


def test_assinatura_do_aviso() -> None:
    manifest = "id:abc123;request-id:req-1;ts:1742505638683;"
    v1 = hmac.new(b"segredo", manifest.encode(), hashlib.sha256).hexdigest()
    header = f"ts=1742505638683,v1={v1}"
    assert verify_signature("segredo", header, "req-1", "ABC123")  # id vai em minúsculas
    assert not verify_signature("outro", header, "req-1", "ABC123")
    assert not verify_signature("segredo", header, "req-2", "ABC123")
    assert not verify_signature("segredo", None, "req-1", "ABC123")
