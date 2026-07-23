import pytest
from fastapi.testclient import TestClient

from sentinal.container import ContainerRuntime
from sentinal.local_api import create_app
from sentinal.state import AgentState


class _FakeRuntime(ContainerRuntime):
    def __init__(self) -> None:
        pass

    def ps(self) -> list[dict]:
        return []


def _client(admin_password: str = "admin") -> TestClient:
    state = AgentState(target_id="test-target")
    app = create_app(state, _FakeRuntime(), admin_password=admin_password)
    return TestClient(app)


def test_login_rejects_wrong_password() -> None:
    client = _client(admin_password="s3cret")
    res = client.post("/api/auth/login", json={"password": "wrong"})
    assert res.status_code == 401


def test_login_accepts_correct_password_and_returns_token() -> None:
    client = _client(admin_password="s3cret")
    res = client.post("/api/auth/login", json={"password": "s3cret"})
    assert res.status_code == 200
    assert "token" in res.json()


def test_protected_endpoints_reject_missing_or_bad_token() -> None:
    client = _client()
    for path in ["/api/score", "/api/findings", "/api/attacks", "/api/settings", "/api/containers"]:
        assert client.get(path).status_code == 401
        assert client.get(path, headers={"Authorization": "Bearer nope"}).status_code == 401


def test_protected_endpoints_accept_valid_token() -> None:
    client = _client(admin_password="s3cret")
    token = client.post("/api/auth/login", json={"password": "s3cret"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/auth/verify", headers=headers).status_code == 200
    assert client.get("/api/score", headers=headers).status_code == 200
    assert client.get("/api/findings", headers=headers).status_code == 200
    assert client.get("/api/attacks", headers=headers).status_code == 200
    assert client.get("/api/containers", headers=headers).status_code == 200

    settings = client.get("/api/settings", headers=headers)
    assert settings.status_code == 200
    body = settings.json()
    assert set(body) == {
        "operator_name",
        "email",
        "department",
        "two_factor_enabled",
        "session_timeout_enabled",
        "ip_whitelist",
        "notify_critical_alerts",
        "notify_log_summaries",
        "notify_marketing",
    }

    updated = client.post("/api/settings", json={"operator_name": "Cmdr. Sterling"}, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["operator_name"] == "Cmdr. Sterling"


def test_attack_resolution_roundtrip() -> None:
    state = AgentState(target_id="test-target-2")
    state.add_attack({"id": "a-1", "type": "log_anomaly", "message": "test"})
    app = create_app(state, _FakeRuntime(), admin_password="s3cret")
    client = TestClient(app)

    token = client.post("/api/auth/login", json={"password": "s3cret"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    res = client.post("/api/attacks/a-1/allow", headers=headers)
    assert res.status_code == 200
    assert res.json() == {"ok": True}


def test_websocket_rejects_bad_token() -> None:
    client = _client(admin_password="s3cret")
    with pytest.raises(Exception):
        with client.websocket_connect("/ws/live?token=wrong"):
            pass
