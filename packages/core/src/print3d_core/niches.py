"""Nichos iniciais do catálogo (spec seções 2.1–2.8).

Nicho é entidade configurável no banco (Fase 2). Este enum é só a *semente*
usada por migrações, testes e metas do Catalogador.
"""

from enum import StrEnum
from typing import Final


class Niche(StrEnum):
    RELIGIOSO = "religioso"
    AUTOMOTIVO = "automotivo"
    CELULAR = "celular"
    BRINDES = "brindes"
    DATAS = "datas-comemorativas"
    FITNESS = "fitness"
    CHAVEIROS = "chaveiros"
    INFANTIL = "infantil"
    CAIXAS = "caixas"


# Meta de produtos únicos por nicho. Soma = 720 (tabela 2.8 da especificação).
NICHE_TARGETS: Final[dict[Niche, int]] = {
    Niche.RELIGIOSO: 300,
    Niche.AUTOMOTIVO: 50,
    Niche.CELULAR: 25,
    Niche.BRINDES: 25,
    Niche.DATAS: 100,
    Niche.FITNESS: 60,
    Niche.CHAVEIROS: 80,
    Niche.INFANTIL: 20,
    Niche.CAIXAS: 60,
}
