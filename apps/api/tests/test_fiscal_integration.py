"""Nota fiscal própria (CI com Postgres): certificado pelo painel, NF-e de pedido do site e do
Mercado Livre com a SEFAZ e o ML simulados — número reservado antes de transmitir, rejeição
reaproveita o número, SEFAZ sem resposta exige consulta, XML anexado no ML e etiqueta."""

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text

from print3d_api.config import Settings, get_settings
from print3d_api.main import create_app
from print3d_api.services import fiscal
from print3d_api.services import mercadolivre as ml_service
from print3d_api.services.cep import Address, CepError, normalize_cep
from print3d_channels.mercadolivre import MercadoLivreError
from print3d_core.security import TokenVault
from print3d_fiscal import Certificado, Retorno, SefazError
from print3d_fiscal.certificado import OID_CNPJ

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_DB_TESTS") != "1", reason="defina RUN_DB_TESTS=1 (CI)"),
]

H = {"x-admin-token": "t"}
API_DIR = Path(__file__).resolve().parents[1]
CNPJ = "11222333000181"
TABLES = (
    "fiscal_invoices, integration_settings, notifications, order_events, order_items, "
    "print_jobs, orders, customers, audit_log"
)


class FakeCep:
    async def lookup(self, cep: str) -> Address:
        digits = normalize_cep(cep)
        if digits.startswith("18"):
            return Address(digits, "Av. Teste", "Vila Gabriel", "Sorocaba", "SP", "3552205")
        if digits.startswith("326"):
            return Address(digits, "Rua MG", "Centro", "Betim", "MG", "3106705")
        raise CepError("CEP não encontrado")


class FakeSefaz:
    """Respostas em fila; sem fila → autoriza."""

    def __init__(self) -> None:
        self.queue: list[Retorno | Exception] = []
        self.sent: list[str] = []
        self.ambientes: list[int] = []

    def factory(self, cert: Certificado, amb: int) -> "FakeSefaz":
        assert cert.cnpj == CNPJ
        self.ambientes.append(amb)
        return self

    def _next(self, chave: str) -> Retorno:
        item = self.queue.pop(0) if self.queue else None
        if isinstance(item, Exception):
            raise item
        if item is not None:
            return item
        return Retorno(
            "100",
            "Autorizado o uso da NF-e",
            protocolo="135260000000001",
            prot_xml=f'<protNFe versao="4.00"><infProt><chNFe>{chave}</chNFe>'
            "<cStat>100</cStat></infProt></protNFe>",
        )

    async def status(self) -> Retorno:
        return Retorno("107", "Servico em Operacao")

    async def autorizar(self, nfe_xml: str) -> Retorno:
        self.sent.append(nfe_xml)
        chave = nfe_xml.split('Id="NFe', 1)[1][:44]
        return self._next(chave)

    async def consultar(self, chave: str) -> Retorno:
        return self._next(chave)

    async def cancelar(
        self, chave: str, protocolo: str, justificativa: str, quando: datetime
    ) -> Retorno:
        if len(justificativa) < 15:
            raise ValueError("a justificativa do cancelamento precisa de 15 a 255 caracteres")
        return Retorno("135", "Evento registrado", protocolo="135260000000009", evento_xml="<r/>")


class FakeML:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, bytes, str]] = []
        self.resources: dict[str, dict[str, Any]] = {
            "/orders/5001": {
                "id": 5001,
                "pack_id": None,
                "shipping": {"id": 4401},
                "buyer": {"billing_info": {"id": "BI1"}},
            }
        }

    async def get(self, token: str, resource: str) -> dict[str, Any]:
        if resource not in self.resources:
            raise MercadoLivreError("not_found", 404, [])
        return self.resources[resource]

    async def billing_info(self, token: str, order: dict[str, Any]) -> dict[str, Any]:
        assert order["buyer"]["billing_info"]["id"] == "BI1"
        return {
            "buyer": {
                "billing_info": {
                    "name": "Ana",
                    "last_name": "Souza",
                    "identification": {"type": "CPF", "number": "123.456.789-09"},
                    "address": {
                        "street_name": "Rua das Rosas",
                        "street_number": "45",
                        "city_name": "Betim",
                        "state": {"code": "MG", "name": "Minas Gerais"},
                        "zip_code": "32600-000",
                        "neighborhood": "Centro",
                    },
                }
            }
        }

    async def upload_fiscal_document(
        self, token: str, pack_id: str, xml: bytes, filename: str
    ) -> dict[str, Any]:
        self.uploads.append((pack_id, xml, filename))
        return {"ids": ["FD1"]}

    async def shipment_label_pdf(self, token: str, shipment_id: str) -> bytes:
        assert shipment_id == "4401"
        return b"%PDF-1.4 etiqueta"


def _pfx() -> bytes:
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"EMPRESA TESTE:{CNPJ}")])
    agora = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(nome)
        .issuer_name(nome)
        .public_key(chave.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(agora - timedelta(days=1))
        .not_valid_after(agora + timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([x509.OtherName(OID_CNPJ, b"\x04\x0e" + CNPJ.encode())]),
            critical=False,
        )
        .sign(chave, hashes.SHA256())
    )
    return pkcs12.serialize_key_and_certificates(
        b"a1", chave, cert, None, serialization.BestAvailableEncryption(b"senha123")
    )


@pytest.fixture
def sefaz() -> FakeSefaz:
    return FakeSefaz()


@pytest.fixture
def fake_ml(monkeypatch: pytest.MonkeyPatch) -> FakeML:
    instance = FakeML()

    async def make_client(session: Any) -> FakeML:
        return instance

    async def token(session: Any) -> str:
        return "ACC"

    monkeypatch.setattr(ml_service, "client", make_client)
    monkeypatch.setattr(ml_service, "access_token", token)
    return instance


@pytest.fixture
def client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sefaz: FakeSefaz, fake_ml: FakeML
) -> Iterator[TestClient]:
    monkeypatch.setenv("FERNET_KEY", TokenVault.generate_key())
    get_settings.cache_clear()
    command.upgrade(Config(str(API_DIR / "alembic.ini")), "head")
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    engine.dispose()
    settings = Settings(
        environment="ci",
        database_url=os.environ["DATABASE_URL"],
        admin_api_token=SecretStr("t"),
        files_dir=str(tmp_path),
    )
    app = create_app(settings)
    app.state.cep_provider = FakeCep()
    app.state.fiscal_factory = sefaz.factory
    with TestClient(app) as c:
        yield c
    get_settings.cache_clear()


def _configure(c: TestClient) -> None:
    res = c.put(
        "/v1/admin/integrations",
        json={
            "values": {
                "FISCAL_AMBIENTE": "homologacao",
                "FISCAL_RAZAO_SOCIAL": "EMPRESA TESTE",
                "FISCAL_IE": "151854851113",
                "FISCAL_CRT": "4",
                "FISCAL_CEP": "18081-000",
                "FISCAL_NUMERO": "802",
                "FISCAL_NCM_PADRAO": "39264000",
                "FISCAL_CFOP_INTERNA": "5101",
                "FISCAL_CFOP_INTERESTADUAL": "6107",
                "FISCAL_CSOSN": "102",
                "FISCAL_OBS": "Documento emitido por ME ou EPP optante pelo Simples Nacional.",
                "FISCAL_ML_CNPJ": "03007331000141",
                "PUBLIC_API_URL": "https://api.loja.test",
            }
        },
        headers=H,
    )
    assert res.status_code == 200, res.text


def _site_order(c: TestClient) -> int:
    cust = c.post(
        "/v1/admin/customers",
        json={"name": "Maria Silva", "document": "529.982.247-25", "email": "m@x.test"},
        headers=H,
    ).json()
    order = c.post(
        "/v1/admin/orders",
        json={
            "channel": "site",
            "customer_id": cust["id"],
            "items": [{"title": "Chaveiro", "quantity": 2, "unit_price": "19.90"}],
            "shipping": "15.00",
            "shipping_address": {
                "cep": "18081-100",
                "street": "Rua A",
                "number": "10",
                "district": "Centro",
                "city": "Sorocaba",
                "uf": "SP",
            },
        },
        headers=H,
    ).json()
    return int(order["id"])


def test_certificado_e_status(client: TestClient, sefaz: FakeSefaz) -> None:
    st = client.get("/v1/admin/fiscal/status", headers=H).json()
    assert st["ready"] is False
    assert "certificado A1" in st["missing"]

    bad = client.post(
        "/v1/admin/fiscal/certificate",
        files={"file": ("a1.pfx", _pfx())},
        data={"senha": "errada"},
        headers=H,
    )
    assert bad.status_code == 422
    ok = client.post(
        "/v1/admin/fiscal/certificate",
        files={"file": ("a1.pfx", _pfx())},
        data={"senha": "senha123"},
        headers=H,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["cnpj"] == CNPJ
    _configure(client)
    st = client.get("/v1/admin/fiscal/status", headers=H).json()
    assert st["ready"] is True
    assert st["ambiente"] == "homologacao"
    assert st["next_number"] == 1
    # a tela Integrações nunca devolve o certificado
    fields = client.get("/v1/admin/integrations", headers=H).json()
    assert all("MII" not in str(f.get("preview")) for f in fields)
    sef = client.post("/v1/admin/fiscal/sefaz-status", headers=H).json()
    assert sef["online"] is True


def _setup(client: TestClient) -> None:
    client.post(
        "/v1/admin/fiscal/certificate",
        files={"file": ("a1.pfx", _pfx())},
        data={"senha": "senha123"},
        headers=H,
    )
    _configure(client)


def test_nfe_do_site(client: TestClient, sefaz: FakeSefaz) -> None:
    _setup(client)
    oid = _site_order(client)
    pre = client.get(f"/v1/admin/orders/{oid}/nfe", headers=H).json()
    assert pre["prefill"]["missing"] == []
    assert pre["prefill"]["recipient"]["cod_municipio"] == "3552205"

    inv = client.post(f"/v1/admin/orders/{oid}/nfe", json={}, headers=H)
    assert inv.status_code == 200, inv.text
    body = inv.json()
    assert body["status"] == "autorizada"
    assert body["number"] == 1
    assert body["total"] == "54.80"  # 2 x 19,90 + 15,00 de frete
    assert "e-mail não configurado" in body["email_status"]
    xml = sefaz.sent[0]
    assert "<CFOP>5101</CFOP>" in xml  # mesmo estado
    assert "<tPag>99</tPag>" in xml  # pedido manual sem forma de pagamento conhecida
    assert "<infIntermed>" not in xml

    again = client.post(f"/v1/admin/orders/{oid}/nfe", json={}, headers=H)
    assert again.status_code == 409

    proc = client.get(f"/v1/admin/nfe/{body['id']}/xml", headers=H)
    assert proc.text.startswith("<?xml")
    assert "<nfeProc" in proc.text

    short = client.post(
        f"/v1/admin/nfe/{body['id']}/cancel", json={"justificativa": "curta"}, headers=H
    )
    assert short.status_code == 422
    canc = client.post(
        f"/v1/admin/nfe/{body['id']}/cancel",
        json={"justificativa": "Pedido cancelado a pedido do cliente"},
        headers=H,
    ).json()
    assert canc["status"] == "cancelada"


def test_nfe_do_ml_com_rejeicao_e_sem_resposta(
    client: TestClient, sefaz: FakeSefaz, fake_ml: FakeML
) -> None:
    _setup(client)
    order = client.post(
        "/v1/admin/orders",
        json={
            "channel": "mercadolivre",
            "external_id": "5001",
            "items": [{"title": "Imagem de Nossa Senhora", "quantity": 2, "unit_price": "25.90"}],
        },
        headers=H,
    ).json()
    oid = order["id"]
    pre = client.get(f"/v1/admin/orders/{oid}/nfe", headers=H).json()["prefill"]
    assert pre["recipient"]["nome"] == "Ana Souza"
    assert pre["recipient"]["uf"] == "MG"
    assert pre["recipient"]["cod_municipio"] == "3106705"

    sefaz.queue.append(Retorno("225", "Rejeicao: Falha no Schema XML"))
    rej = client.post(f"/v1/admin/orders/{oid}/nfe", json={}, headers=H).json()
    assert rej["status"] == "rejeitada"
    assert rej["number"] == 1

    sefaz.queue.append(SefazError("sem resposta da SEFAZ (ConnectTimeout)"))
    lost = client.post(f"/v1/admin/orders/{oid}/nfe", json={}, headers=H)
    assert lost.status_code == 502
    # não emite de novo sem consultar (evita nota em dobro)
    assert client.post(f"/v1/admin/orders/{oid}/nfe", json={}, headers=H).status_code == 409

    inv = client.get(f"/v1/admin/orders/{oid}/nfe", headers=H).json()["invoices"][0]
    assert inv["number"] == 1  # a rejeitada foi reaproveitada
    assert inv["status"] == "sem_resposta"
    done = client.post(f"/v1/admin/nfe/{inv['id']}/consult", headers=H).json()
    assert done["status"] == "autorizada"
    xml = sefaz.sent[-1]
    assert "<CFOP>6107</CFOP>" in xml  # outro estado
    assert "<idDest>2</idDest>" in xml
    assert "<indIntermed>1</indIntermed>" in xml
    assert "<CNPJ>03007331000141</CNPJ>" in xml
    # homologação: nome do destinatário trocado pela regra da SEFAZ
    assert "NF-E EMITIDA EM AMBIENTE DE HOMOLOGACAO" in xml

    assert fake_ml.uploads[0][0] == "5001"  # sem pack: id do pedido
    assert fake_ml.uploads[0][2].endswith(".xml")
    assert "anexado" in done["ml_status"]

    token = fiscal.label_token(oid)
    pdf = client.get(f"/v1/channels/etiqueta/{token}")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert client.get("/v1/channels/etiqueta/" + "x" * 40).status_code == 404
