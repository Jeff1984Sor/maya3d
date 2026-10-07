"""Ciclo de vida do pedido (spec 5.0): estados, transições permitidas e impressão digital.

Puro: sem banco. A API usa isto para validar cada toque nos botões da tela Produção.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any, Final


class OrderStatus(StrEnum):
    PAGO = "pago"
    IMPRIMINDO_AMOSTRA = "imprimindo_amostra"
    AMOSTRA_PRONTA = "amostra_pronta"
    AJUSTE_SOLICITADO = "ajuste_solicitado"
    NA_FILA = "na_fila"
    IMPRIMINDO = "imprimindo"
    ACABAMENTO = "acabamento"
    EMBALADO = "embalado"
    SAIU_PARA_ENTREGA = "saiu_para_entrega"  # entrega local (Sorocaba)
    ENVIADO = "enviado"
    ENTREGUE = "entregue"
    CANCELADO = "cancelado"


S = OrderStatus

TRANSITIONS: Final[dict[OrderStatus, frozenset[OrderStatus]]] = {
    S.PAGO: frozenset({S.NA_FILA, S.IMPRIMINDO_AMOSTRA, S.CANCELADO}),
    S.IMPRIMINDO_AMOSTRA: frozenset({S.AMOSTRA_PRONTA, S.CANCELADO}),
    S.AMOSTRA_PRONTA: frozenset({S.NA_FILA, S.AJUSTE_SOLICITADO, S.CANCELADO}),
    S.AJUSTE_SOLICITADO: frozenset({S.IMPRIMINDO_AMOSTRA, S.CANCELADO}),
    S.NA_FILA: frozenset({S.IMPRIMINDO, S.CANCELADO}),
    S.IMPRIMINDO: frozenset({S.ACABAMENTO}),
    S.ACABAMENTO: frozenset({S.EMBALADO}),
    S.EMBALADO: frozenset({S.ENVIADO, S.SAIU_PARA_ENTREGA}),
    S.SAIU_PARA_ENTREGA: frozenset({S.ENTREGUE}),
    S.ENVIADO: frozenset({S.ENTREGUE}),
    S.ENTREGUE: frozenset(),
    S.CANCELADO: frozenset(),
}

# Rótulos para o cliente (linha do tempo em "Meus pedidos" e mensagens).
CUSTOMER_LABELS: Final[dict[OrderStatus, str]] = {
    S.PAGO: "Pagamento confirmado",
    S.IMPRIMINDO_AMOSTRA: "Imprimindo a amostra",
    S.AMOSTRA_PRONTA: "Amostra pronta para sua aprovação",
    S.AJUSTE_SOLICITADO: "Ajuste solicitado",
    S.NA_FILA: "Na fila de impressão",
    S.IMPRIMINDO: "Imprimindo",
    S.ACABAMENTO: "Acabamento",
    S.EMBALADO: "Embalado",
    S.SAIU_PARA_ENTREGA: "Saiu para entrega",
    S.ENVIADO: "Enviado",
    S.ENTREGUE: "Entregue",
    S.CANCELADO: "Cancelado",
}

# Botões grandes da tela Produção: próximo passo "natural" de cada estado.
NEXT_STEP: Final[dict[OrderStatus, OrderStatus]] = {
    S.PAGO: S.NA_FILA,
    S.NA_FILA: S.IMPRIMINDO,
    S.IMPRIMINDO: S.ACABAMENTO,
    S.ACABAMENTO: S.EMBALADO,
    S.EMBALADO: S.ENVIADO,
    S.SAIU_PARA_ENTREGA: S.ENTREGUE,
    S.ENVIADO: S.ENTREGUE,
    S.IMPRIMINDO_AMOSTRA: S.AMOSTRA_PRONTA,
}


class TransitionError(Exception):
    pass


def check_transition(current: str, target: str) -> OrderStatus:
    try:
        cur, tgt = OrderStatus(current), OrderStatus(target)
    except ValueError as exc:
        raise TransitionError(f"status desconhecido: {current} → {target}") from exc
    if tgt not in TRANSITIONS[cur]:
        allowed = ", ".join(sorted(TRANSITIONS[cur])) or "nenhum (estado final)"
        raise TransitionError(f"não dá para ir de '{cur}' para '{tgt}' (permitido: {allowed})")
    return tgt


def needs_sample(quantity: int, threshold: int, already_produced: bool) -> bool:
    """Amostra quando a quantidade passa do limite e a combinação nunca foi produzida."""
    return quantity > threshold and not already_produced


def fingerprint(
    variant_id: int | None,
    personalization: Mapping[str, Any],
    material_ids: Sequence[int],
) -> str:
    """Hash estável da combinação design/variante + personalização + materiais/cores."""
    canonical = json.dumps(
        {
            "variant": variant_id,
            "personalization": personalization,
            "materials": sorted(material_ids),
        },
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def material_key(material_ids: Sequence[int]) -> str:
    """Chave de agrupamento da fila: peças com os mesmos materiais/cores imprimem juntas."""
    return "+".join(str(m) for m in sorted(set(material_ids))) or "sem-material"
