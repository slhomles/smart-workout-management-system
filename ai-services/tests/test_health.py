from fastapi.testclient import TestClient

from app.core.models import registry


def test_health_without_models_returns_ok(client: TestClient) -> None:
    res = client.get("/health")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["models"] == {}
    assert body["checked_at"].endswith(("Z", "+00:00"))
    assert res.headers["X-Request-ID"].startswith("req_")


def test_health_lists_ready_model_versions(client: TestClient) -> None:
    registry.register("recovery")
    registry.mark_ready("recovery", "heuristic-v1")
    registry.register("equipment", required=False)

    body = client.get("/health").json()

    assert body["models"] == {"equipment": None, "recovery": "heuristic-v1"}


def test_health_required_model_not_ready_returns_503(client: TestClient) -> None:
    registry.register("equipment")

    res = client.get("/health", headers={"X-Request-ID": "req_test0001"})

    assert res.status_code == 503
    assert res.json() == {"error": {"code": "service_unavailable", "message": "Model AI chưa sẵn sàng",
                                    "details": [], "request_id": "req_test0001"}}
