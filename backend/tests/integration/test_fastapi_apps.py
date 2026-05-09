from fastapi.testclient import TestClient

from app import ai as agent_app
from app import app as backend_app
from app import mcp as mcp_app
from app.api.v1.endpoints import utils


def test_backend_app_client_log_endpoint_without_lifespan():
    client = TestClient(backend_app.app)

    response = client.post(
        "/api/v1/client-log/log",
        json={"event": "rate_limited", "level": "not-real", "sku": "dynamic_maps", "context": {"a": 1}},
        headers={"user-agent": "pytest"},
    )

    assert response.status_code == 200
    assert response.json() == {"status_code": 200}


def test_backend_app_timezone_endpoint_uses_mocked_tool(monkeypatch):
    async def fake_timezone(lat, lng, timestamp=None, timeout_seconds=None):
        return {"timeZoneId": {"value": "America/Los_Angeles"}}

    monkeypatch.setattr(utils, "get_timezone_tool", fake_timezone)
    client = TestClient(backend_app.app)

    response = client.post("/api/v1/utils/get-timezone", params={"lat": 37.7, "lng": -122.4})

    assert response.status_code == 200
    assert response.json() == {"timezoneId": "America/Los_Angeles"}


def test_backend_app_timezone_endpoint_falls_back_on_tool_error(monkeypatch):
    async def broken_timezone(*args, **kwargs):
        raise RuntimeError("network blocked")

    monkeypatch.setattr(utils, "get_timezone_tool", broken_timezone)
    client = TestClient(backend_app.app)

    response = client.post("/api/v1/utils/get-timezone", params={"lat": 0, "lng": 0})

    assert response.status_code == 200
    assert response.json() == {"timezoneId": "UTC"}


def test_agent_chat_endpoint_rejects_missing_auth_before_db_access():
    client = TestClient(agent_app.app)

    response = client.post("/agent/api/v1/chat/trip-1", json={"message": "hello"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing or invalid Authorization header."


def test_agent_app_has_expected_routes_registered():
    paths = {route.path for route in agent_app.app.routes}

    assert "/agent/api/v1/chat/{trip_id}" in paths
    assert "/agent/api/v1/solo-planner/generate/solo/{id}" in paths


def test_mcp_app_has_expected_sse_route_registered():
    paths = {route.path for route in mcp_app.app.routes}

    assert "/mcp/sse" in paths
