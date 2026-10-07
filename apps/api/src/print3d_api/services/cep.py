"""Consulta de CEP (ViaCEP): cidade e código IBGE. A regra de entrega local usa o código IBGE,
nunca faixa de CEP fixa no código (spec 2.9)."""

import re
from dataclasses import dataclass
from typing import Protocol

import httpx


class CepError(Exception):
    pass


@dataclass(frozen=True)
class Address:
    cep: str
    street: str
    district: str
    city: str
    uf: str
    ibge: str


class CepProvider(Protocol):
    async def lookup(self, cep: str) -> Address: ...


def normalize_cep(cep: str) -> str:
    digits = re.sub(r"\D", "", cep)
    if len(digits) != 8:
        raise CepError("CEP deve ter 8 dígitos")
    return digits


class ViaCepProvider:
    def __init__(self, base_url: str = "https://viacep.com.br/ws", timeout: float = 5.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._cache: dict[str, Address] = {}

    async def lookup(self, cep: str) -> Address:
        digits = normalize_cep(cep)
        if digits in self._cache:
            return self._cache[digits]
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                res = await client.get(f"{self._base}/{digits}/json/")
            data = res.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise CepError("não foi possível consultar o CEP agora") from exc
        if res.status_code != 200 or data.get("erro"):
            raise CepError("CEP não encontrado")
        address = Address(
            cep=digits,
            street=data.get("logradouro", ""),
            district=data.get("bairro", ""),
            city=data.get("localidade", ""),
            uf=data.get("uf", ""),
            ibge=str(data.get("ibge", "")),
        )
        self._cache[digits] = address
        return address
