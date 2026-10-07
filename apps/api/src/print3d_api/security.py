"""Proteção das rotas de admin até existir login de verdade (Fase 5/6, com HTTPS).

Token estático em header, comparado em tempo constante. Sem token configurado no ambiente,
as rotas de admin respondem 503: nunca ficam abertas por esquecimento.
"""

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from print3d_api.config import Settings
from print3d_api.deps import get_app_settings


def require_admin(
    settings: Annotated[Settings, Depends(get_app_settings)],
    x_admin_token: Annotated[str | None, Header()] = None,
) -> None:
    expected = settings.admin_api_token
    if expected is None or not expected.get_secret_value():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "admin desabilitado: defina ADMIN_API_TOKEN"
        )
    if x_admin_token is None or not hmac.compare_digest(
        x_admin_token.encode(), expected.get_secret_value().encode()
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token de admin inválido")
