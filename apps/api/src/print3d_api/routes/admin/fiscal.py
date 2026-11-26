"""Painel → Nota fiscal: certificado, situação da SEFAZ e NF-e de cada pedido."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.db.session import get_session
from print3d_api.models import FiscalInvoice, Order
from print3d_api.routes.store import Cep
from print3d_api.services import fiscal

router = APIRouter(tags=["admin: nota fiscal"])
Session = Annotated[AsyncSession, Depends(get_session)]


def get_factory(request: Request) -> fiscal.TransmissorFactory:
    """Testes trocam a SEFAZ por um falso em app.state.fiscal_factory."""
    factory: fiscal.TransmissorFactory | None = getattr(request.app.state, "fiscal_factory", None)
    return factory or fiscal.default_transmissor


Factory = Annotated[fiscal.TransmissorFactory, Depends(get_factory)]


def _http(exc: fiscal.FiscalError) -> HTTPException:
    return HTTPException(exc.status, str(exc))


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    order_id: int
    ambiente: int
    serie: int
    number: int
    status: str
    chave: str | None
    cstat: str | None
    motivo: str | None
    protocolo: str | None
    total: Decimal
    recipient: dict[str, Any]
    authorized_at: datetime | None
    ml_status: str | None
    email_status: str | None
    created_at: datetime


class RecipientIn(BaseModel):
    nome: str = Field(min_length=2, max_length=60)
    documento: str = Field(min_length=11, max_length=18)
    email: str | None = Field(default=None, max_length=60)
    ie: str | None = Field(default=None, max_length=14)
    cep: str = Field(min_length=8, max_length=9)
    logradouro: str = Field(default="", max_length=60)
    numero: str = Field(default="", max_length=60)
    complemento: str | None = Field(default=None, max_length=60)
    bairro: str = Field(default="", max_length=60)
    municipio: str = Field(default="", max_length=60)
    uf: str = Field(default="", max_length=2)
    cod_municipio: str = Field(default="", max_length=7)


class EmitIn(BaseModel):
    recipient: RecipientIn | None = None  # vazio = usa os dados do pedido / do ML


class CancelIn(BaseModel):
    justificativa: str = Field(min_length=15, max_length=255)


@router.get("/fiscal/status")
async def get_status(session: Session) -> dict[str, Any]:
    return await fiscal.status(session)


@router.post("/fiscal/certificate")
async def upload_certificate(
    session: Session,
    file: Annotated[UploadFile, File()],
    senha: Annotated[str, Form(min_length=1, max_length=200)],
) -> dict[str, Any]:
    """Recebe o .pfx/.p12 e a senha; confere e guarda cifrado. Nunca devolve o arquivo."""
    data = await file.read(64_001)
    try:
        return await fiscal.save_certificate(session, data, senha)
    except fiscal.FiscalError as exc:
        raise _http(exc) from exc


@router.post("/fiscal/sefaz-status")
async def sefaz_status(session: Session, factory: Factory) -> dict[str, Any]:
    try:
        return await fiscal.sefaz_status(session, factory)
    except fiscal.FiscalError as exc:
        raise _http(exc) from exc


@router.get("/orders/{order_id}/nfe")
async def order_nfe(order_id: int, session: Session, cep: Cep) -> dict[str, Any]:
    """Notas do pedido + destinatário sugerido para emitir."""
    order = await session.get(Order, order_id)
    if order is None:
        raise HTTPException(404, "pedido não existe")
    invoices = await fiscal.list_for_order(session, order_id)
    return {
        "ambiente": await fiscal.current_ambiente(session),
        "invoices": [InvoiceOut.model_validate(i).model_dump(mode="json") for i in invoices],
        "prefill": await fiscal.prefill(session, order, cep),
    }


@router.post("/orders/{order_id}/nfe", response_model=InvoiceOut)
async def emit(
    order_id: int, payload: EmitIn, session: Session, cep: Cep, factory: Factory
) -> FiscalInvoice:
    recipient = payload.recipient.model_dump() if payload.recipient else None
    try:
        return await fiscal.emit(session, order_id, recipient, cep, factory)
    except fiscal.FiscalError as exc:
        raise _http(exc) from exc


@router.post("/nfe/{invoice_id}/consult", response_model=InvoiceOut)
async def consult(invoice_id: int, session: Session, factory: Factory) -> FiscalInvoice:
    try:
        return await fiscal.consult(session, invoice_id, factory)
    except fiscal.FiscalError as exc:
        raise _http(exc) from exc


@router.post("/nfe/{invoice_id}/cancel", response_model=InvoiceOut)
async def cancel(
    invoice_id: int, payload: CancelIn, session: Session, factory: Factory
) -> FiscalInvoice:
    """Cancela na SEFAZ (prazo legal: 24 h após a autorização). Ação sem volta."""
    try:
        return await fiscal.cancel(session, invoice_id, payload.justificativa, factory)
    except fiscal.FiscalError as exc:
        raise _http(exc) from exc


@router.post("/nfe/{invoice_id}/resend", response_model=InvoiceOut)
async def resend(invoice_id: int, session: Session) -> FiscalInvoice:
    """Repete o pós-autorização: XML na venda do ML e e-mail com a etiqueta."""
    try:
        return await fiscal.resend(session, invoice_id)
    except fiscal.FiscalError as exc:
        raise _http(exc) from exc


@router.get("/nfe/{invoice_id}/xml")
async def download_xml(invoice_id: int, session: Session) -> Response:
    inv = await session.get(FiscalInvoice, invoice_id)
    if inv is None or not (inv.proc_xml or inv.xml):
        raise HTTPException(404, "nota sem XML")
    return Response(
        (inv.proc_xml or inv.xml or "").encode("utf-8"),
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="NFe{inv.chave}.xml"'},
    )


@router.get("/nfe/{invoice_id}/danfe")
async def download_danfe(invoice_id: int, session: Session) -> Response:
    inv = await session.get(FiscalInvoice, invoice_id)
    if inv is None or inv.status not in ("autorizada", "cancelada"):
        raise HTTPException(404, "DANFE só de nota autorizada")
    try:
        pdf = fiscal.danfe_pdf(inv)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="DANFE-{inv.number}.pdf"'},
    )
