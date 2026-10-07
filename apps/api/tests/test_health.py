from fastapi.testclient import TestClient

from print3d_api.health import CheckResult, HealthChecker


class StubChecker(HealthChecker):
    def __init__(self, results: dict[str, CheckResult]) -> None:
        self._results = results

    async def run(self) -> dict[str, CheckResult]:
        return self._results


def test_live(client: TestClient) -> None:
    res = client.get("/health/live")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "release": "test-sha", "environment": "ci"}
    assert res.headers["x-request-id"]


def test_request_id_e_propagado(client: TestClient) -> None:
    res = client.get("/health/live", headers={"x-request-id": "abc123"})
    assert res.headers["x-request-id"] == "abc123"


def test_ready_ok(client: TestClient) -> None:
    res = client.get("/health/ready")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_ready_degradado_devolve_503(client: TestClient) -> None:
    client.app.state.health_checker = StubChecker(  # type: ignore[attr-defined]
        {"database": CheckResult(False, "OperationalError"), "redis": CheckResult(True)}
    )
    res = client.get("/health/ready")
    assert res.status_code == 503
    body = res.json()
    assert body["status"] == "degraded"
    assert body["checks"]["database"] == {"ok": False, "detail": "OperationalError"}
