"""Proteção das rotas de admin até existir login de verdade (Fase 5/6, com HTTPS).

- X-Admin-Token: token estático do servidor (o painel usa), comparado em tempo constante.
- X-Robot-Token: token temporário gerado no painel para automações do dono (7 dias,
  revogável, cifrado no banco). Só consulta o banco quando esse cabeçalho vem.
Sem ADMIN_API_TOKEN configurado, as rotas de admin respondem 503: nunca ficam abertas.
"""

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from print3d_api.config import Settings
from print3d_api.deps import get_app_settings
from print3d_api.services import robot


async def require_admin(
    request: Request,
    settings: Annotated[Settings, Depends(get_app_settings)],
    x_admin_token: Annotated[str | None, Header()] = None,
    x_robot_token: Annotated[str | None, Header()] = None,
) -> None:
    expected = settings.admin_api_token
    if expected is None or not expected.get_secret_value():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "admin desabilitado: defina ADMIN_API_TOKEN"
        )
    if x_admin_token is not None and hmac.compare_digest(
        x_admin_token.encode(), expected.get_secret_value().encode()
    ):
        return
    if x_robot_token:
        async with request.app.state.session_factory() as session:
            if await robot.is_valid(session, x_robot_token):
                return
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token de admin inválido")
