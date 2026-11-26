"""Assinatura XMLDSig envelopada (padrão NF-e: C14N 1.0, RSA-SHA1, referência por Id)."""

import base64
import hashlib
from typing import Protocol

from print3d_fiscal.xmlc import el

DSIG = "http://www.w3.org/2000/09/xmldsig#"
C14N = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"


class Assinador(Protocol):
    def assinar_sha1(self, dados: bytes) -> bytes: ...

    def der_base64(self) -> str: ...


def _alg(tag: str, algoritmo: str) -> str:
    return el(tag, attrs={"Algorithm": algoritmo})


def _signed_info(ref_id: str, digest: str, ns: str | None) -> str:
    return el(
        "SignedInfo",
        _alg("CanonicalizationMethod", C14N),
        _alg("SignatureMethod", DSIG + "rsa-sha1"),
        el(
            "Reference",
            el(
                "Transforms",
                _alg("Transform", DSIG + "enveloped-signature"),
                _alg("Transform", C14N),
            ),
            _alg("DigestMethod", DSIG + "sha1"),
            el("DigestValue", digest),
            attrs={"URI": f"#{ref_id}"},
        ),
        ns=ns,
    )


def assinar(elemento_canonico: str, ref_id: str, assinador: Assinador) -> str:
    """`elemento_canonico`: o elemento referenciado em C14N, já com o xmlns herdado do pai.
    Devolve o bloco <Signature> para colocar logo depois dele."""
    digest = base64.b64encode(
        hashlib.sha1(elemento_canonico.encode("utf-8")).digest()  # noqa: S324
    ).decode()
    # Na forma canônica o SignedInfo carrega o xmlns herdado do <Signature>.
    canonico = _signed_info(ref_id, digest, ns=DSIG)
    valor = base64.b64encode(assinador.assinar_sha1(canonico.encode("utf-8"))).decode()
    return el(
        "Signature",
        _signed_info(ref_id, digest, ns=None),
        el("SignatureValue", valor),
        el("KeyInfo", el("X509Data", el("X509Certificate", assinador.der_base64()))),
        ns=DSIG,
    )
