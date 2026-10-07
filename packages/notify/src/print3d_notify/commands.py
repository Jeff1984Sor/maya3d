"""Comandos do dono pelo WhatsApp (spec 5.0, 'operação pelo WhatsApp').

Parser determinístico e conservador; mensagens que não casam com nenhum comando recebem a
ajuda. (Um agente de IA com áudio/foto entra por cima depois, usando os mesmos comandos.)
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

Kind = Literal["avancar", "fila", "vendas", "entregas", "ajuda", "desconhecido"]

# palavra falada → status do pedido
STATUS_WORDS = {
    "pago": "pago",
    "pix": "pago",
    "fila": "na_fila",
    "imprimindo": "imprimindo",
    "acabamento": "acabamento",
    "embalado": "embalado",
    "enviado": "enviado",
    "saiu": "saiu_para_entrega",
    "entregue": "entregue",
    "amostra pronta": "amostra_pronta",
    "aprovado": "na_fila",
}

HELP = (
    "Comandos:\n"
    "• 1234 pago — confirma o Pix e manda para produção\n"
    "• 1234 imprimindo / acabamento / embalado / enviado / entregue\n"
    "• amostra pronta 1234 (com foto) — pede aprovação ao cliente\n"
    "• fila — o que tenho para imprimir\n"
    "• vendas — resumo da semana\n"
    "• entregas — entregas locais de hoje"
)


@dataclass(frozen=True)
class Command:
    kind: Kind
    order_number: int | None = None
    status: str | None = None


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower().strip()


def parse(text: str) -> Command:
    t = _fold(text)
    if not t:
        return Command("desconhecido")
    if t in ("ajuda", "help", "comandos", "?"):
        return Command("ajuda")
    if re.search(r"\b(fila|imprimir hoje|pra imprimir|para imprimir)\b", t) and not re.search(
        r"\d", t
    ):
        return Command("fila")
    if re.search(r"\b(vendas|vendi|faturamento)\b", t):
        return Command("vendas")
    if re.search(r"\bentregas\b", t):
        return Command("entregas")
    number = re.search(r"#?\b(\d{3,7})\b", t)
    if number:
        rest = (t[: number.start()] + " " + t[number.end() :]).strip()
        for word in sorted(STATUS_WORDS, key=len, reverse=True):
            if re.search(rf"\b{word}\b", rest):
                return Command(
                    "avancar", order_number=int(number.group(1)), status=STATUS_WORDS[word]
                )
    return Command("desconhecido")
