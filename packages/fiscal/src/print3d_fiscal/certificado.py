"""Certificado digital A1 (arquivo .pfx/.p12 + senha) — chave privada e certificado X.509.

O arquivo chega pelo painel (cifrado no banco); aqui só vive em memória. Para o TLS mútuo
com a SEFAZ o `ssl` do Python exige arquivos: gravamos PEMs temporários com permissão 0600
e apagamos logo após carregar no contexto.
"""

import base64
import os
import re
import ssl
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

# ICP-Brasil: CNPJ do titular no "otherName" 2.16.76.1.3.3 do certificado e-CNPJ
OID_CNPJ = x509.ObjectIdentifier("2.16.76.1.3.3")


class CertificadoError(Exception):
    pass


@dataclass(frozen=True)
class Certificado:
    chave: rsa.RSAPrivateKey
    cert: x509.Certificate
    cadeia: tuple[x509.Certificate, ...]

    @property
    def titular(self) -> str:
        attrs = self.cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
        return str(attrs[0].value) if attrs else ""

    @property
    def cnpj(self) -> str | None:
        try:
            san = self.cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
            for nome in san.value:
                if isinstance(nome, x509.OtherName) and nome.type_id == OID_CNPJ:
                    digitos = re.sub(rb"\D", b"", nome.value).decode()
                    if len(digitos) >= 14:
                        return digitos[-14:]
        except x509.ExtensionNotFound:
            pass
        achado = re.search(r":(\d{14})\b", self.titular)
        return achado.group(1) if achado else None

    @property
    def valido_ate(self) -> datetime:
        return self.cert.not_valid_after_utc

    @property
    def valido_desde(self) -> datetime:
        return self.cert.not_valid_before_utc

    def vencido(self, agora: datetime | None = None) -> bool:
        agora = agora or datetime.now(UTC)
        return not (self.valido_desde <= agora <= self.valido_ate)

    def der_base64(self) -> str:
        return base64.b64encode(self.cert.public_bytes(serialization.Encoding.DER)).decode()

    def assinar_sha1(self, dados: bytes) -> bytes:
        # O padrão da NF-e (MOC 4.00) ainda é RSA-SHA1 na assinatura XML.
        return self.chave.sign(dados, padding.PKCS1v15(), hashes.SHA1())  # noqa: S303

    def contexto_tls(self) -> ssl.SSLContext:
        """TLS mútuo: verifica a SEFAZ pela raiz ICP-Brasil e apresenta nosso certificado."""
        raiz = resources.files("print3d_fiscal").joinpath("icp_brasil_v10.pem").read_text()
        ctx = ssl.create_default_context(cadata=raiz)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        chave_pem = self.chave.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        certs_pem = b"".join(
            c.public_bytes(serialization.Encoding.PEM) for c in (self.cert, *self.cadeia)
        )
        with tempfile.TemporaryDirectory(prefix="nfe-") as pasta:
            caminho_chave = os.path.join(pasta, "k.pem")
            caminho_cert = os.path.join(pasta, "c.pem")
            for caminho, conteudo in ((caminho_chave, chave_pem), (caminho_cert, certs_pem)):
                fd = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as f:
                    f.write(conteudo)
            ctx.load_cert_chain(caminho_cert, caminho_chave)
        return ctx


def carregar_pfx(dados: bytes, senha: str) -> Certificado:
    try:
        chave, cert, extras = pkcs12.load_key_and_certificates(dados, senha.encode())
    except ValueError as exc:
        raise CertificadoError("senha errada ou arquivo de certificado inválido") from exc
    if cert is None or chave is None:
        raise CertificadoError("o arquivo não tem certificado com chave privada (precisa ser A1)")
    if not isinstance(chave, rsa.RSAPrivateKey):
        raise CertificadoError("certificado sem chave RSA (não é um A1 da ICP-Brasil)")
    return Certificado(chave=chave, cert=cert, cadeia=tuple(extras or ()))


def carregar_pfx_base64(conteudo_b64: str, senha: str) -> Certificado:
    try:
        dados = base64.b64decode(conteudo_b64, validate=True)
    except ValueError as exc:
        raise CertificadoError("arquivo de certificado corrompido") from exc
    return carregar_pfx(dados, senha)
