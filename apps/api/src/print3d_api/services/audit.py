"""Registro de auditoria (spec: toda decisão automática vai para o AuditLog com motivo)."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.models import AuditLog


async def record(
    session: AsyncSession,
    *,
    actor: str,
    action: str,
    decision: str | None = None,
    reason: str | None = None,
    entity_type: str | None = None,
    entity_id: str | int | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditLog:
    """Adiciona à sessão; quem chama decide o commit (junto com a ação auditada)."""
    entry = AuditLog(
        actor=actor,
        action=action,
        decision=decision,
        reason=reason,
        entity_type=entity_type,
        entity_id=None if entity_id is None else str(entity_id),
        payload=payload or {},
    )
    session.add(entry)
    await session.flush()
    return entry
