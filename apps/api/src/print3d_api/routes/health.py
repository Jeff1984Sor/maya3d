from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from print3d_api.config import Settings
from print3d_api.deps import get_app_settings, get_health_checker
from print3d_api.health import HealthChecker

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live(settings: Annotated[Settings, Depends(get_app_settings)]) -> dict[str, str]:
    """Processo de pé. Não toca em dependências."""
    return {"status": "ok", "release": settings.release, "environment": settings.environment}


@router.get("/ready")
async def ready(
    response: Response,
    checker: Annotated[HealthChecker, Depends(get_health_checker)],
) -> dict[str, object]:
    """Dependências (Postgres, Redis) respondendo."""
    results = await checker.run()
    healthy = all(r.ok for r in results.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if healthy else "degraded",
        "checks": {name: {"ok": r.ok, "detail": r.detail} for name, r in results.items()},
    }
