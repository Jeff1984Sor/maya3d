"""Chave de acesso da NF-e (44 dígitos) e dígito verificador módulo 11 (MOC, anexo I)."""

import secrets
from dataclasses import dataclass
from datetime import datetime


def dv_mod11(numero: str) -> int:
    soma, peso = 0, 2
    for d in reversed(numero):
        soma += int(d) * peso
        peso = 2 if peso == 9 else peso + 1
    resto = soma % 11
    return 0 if resto in (0, 1) else 11 - resto


def codigo_numerico(numero_nota: int) -> str:
    """cNF aleatório de 8 dígitos, diferente do número da nota (regra de validação)."""
    while True:
        cnf = f"{secrets.randbelow(10**8):08d}"
        if int(cnf) != numero_nota:
            return cnf


@dataclass(frozen=True)
class Chave:
    cuf: str
    emissao: datetime
    cnpj: str
    modelo: int
    serie: int
    numero: int
    tp_emis: int
    cnf: str

    @property
    def sem_dv(self) -> str:
        s = (
            f"{self.cuf}{self.emissao:%y%m}{self.cnpj:0>14}{self.modelo:02d}"
            f"{self.serie:03d}{self.numero:09d}{self.tp_emis}{self.cnf}"
        )
        if len(s) != 43 or not s.isdigit():
            raise ValueError("dados da chave de acesso inválidos")
        return s

    @property
    def dv(self) -> int:
        return dv_mod11(self.sem_dv)

    @property
    def valor(self) -> str:
        return f"{self.sem_dv}{self.dv}"
