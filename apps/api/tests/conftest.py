from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from print3d_api.config import Settings
from print3d_api.health import CheckResult, HealthChecker
from print3d_api.main import create_app


class _OkChecker(HealthChecker):
    def __init__(self) -> None:  # sem engine/redis reais
        pass

    async def run(self) -> dict[str, CheckResult]:
        return {"database": CheckResult(True), "redis": CheckResult(True)}


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="ci", release="test-sha")


@pytest.fixture
def client(settings: Settings) -> TestClient:
    # Sem `with`: o lifespan (engine/redis reais) não roda; injetamos stubs em app.state.
    app = create_app(settings)
    app.state.health_checker = _OkChecker()
    app.state.session_factory = MagicMock(return_value=AsyncMock())
    return TestClient(app)
