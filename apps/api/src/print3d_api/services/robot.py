"""Token de robô: acesso temporário à API do painel para automações do dono (ex.: importar o
acervo do computador dele). Gerado no painel, mostrado UMA vez, guardado cifrado, vale 7 dias
e pode ser revogado. Cada uso aparece na auditoria pelo ator "robo".
"""

import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from print3d_api.models import IntegrationSetting
from print3d_api.services import audit, integrations

TOKEN_KEY = "ROBOT_TOKEN"  # noqa: S105 — nome da chave na tabela, não o segredo
EXPIRES_KEY = "ROBOT_TOKEN_EXPIRES"
VALIDITY = timedelta(days=7)


class RobotError(Exception):
    pass


async def issue(session: AsyncSession) -> tuple[str, datetime]:
    vault = integrations.vault()
    if vault is None:
        raise RobotError("servidor sem FERNET_KEY: não dá para guardar o token")
    token = "rb_" + secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + VALIDITY
    for key, value, secret in (
        (TOKEN_KEY, vault.encrypt(token), True),
        (EXPIRES_KEY, expires.isoformat(), False),
    ):
        row = await session.get(IntegrationSetting, key)
        if row is None:
            session.add(IntegrationSetting(key=key, value=value, secret=secret))
        else:
            row.value, row.secret = value, secret
    await audit.record(
        session,
        actor="admin",
        action="token_robo_gerado",
        payload={"vale_ate": expires.isoformat()},
    )
    await session.commit()
    return token, expires


async def revoke(session: AsyncSession) -> None:
    for key in (TOKEN_KEY, EXPIRES_KEY):
        row = await session.get(IntegrationSetting, key)
        if row is not None:
            await session.delete(row)
    await audit.record(session, actor="admin", action="token_robo_revogado")
    await session.commit()


async def status(session: AsyncSession) -> dict[str, Any]:
    expires = await session.get(IntegrationSetting, EXPIRES_KEY)
    if expires is None:
        return {"active": False, "expires_at": None}
    when = datetime.fromisoformat(expires.value)
    return {"active": when > datetime.now(UTC), "expires_at": when.isoformat()}


async def is_valid(session: AsyncSession, presented: str) -> bool:
    token_row = await session.get(IntegrationSetting, TOKEN_KEY)
    expires_row = await session.get(IntegrationSetting, EXPIRES_KEY)
    vault = integrations.vault()
    if token_row is None or expires_row is None or vault is None:
        return False
    if datetime.fromisoformat(expires_row.value) <= datetime.now(UTC):
        return False
    try:
        expected = vault.decrypt(token_row.value)
    except Exception:
        return False
    return hmac.compare_digest(presented.encode(), expected.encode())
