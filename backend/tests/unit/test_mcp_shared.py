import asyncio

import pytest

from app.agent.mcp_server.tools import _errors, _shared


def run(coro):
    return asyncio.run(coro)


def test_normalize_waypoint_accepts_all_supported_shapes():
    assert run(_shared.normalize_waypoint(_shared.Waypoint(address="Taj Mahal"))) == {"address": "Taj Mahal"}
    assert run(_shared.normalize_waypoint({"lat": 1, "lng": 2})) == {"location": {"latLng": {"latitude": 1.0, "longitude": 2.0}}}
    assert run(_shared.normalize_waypoint({"place_id": "abc"})) == {"placeId": "abc"}


def test_normalize_waypoint_rejects_missing_location():
    with pytest.raises(ValueError):
        run(_shared.normalize_waypoint({}))


def test_parse_mcp_location_and_validation_error():
    assert run(_shared.parse_mcp_location({"address": "A"})) == ("A", "")
    assert run(_shared.parse_mcp_location({"location": {"latLng": {"latitude": 1, "longitude": 2}}})) == ("1,2", "")
    assert run(_shared.parse_mcp_location({"placeId": "pid"})) == ("Saved Location", "pid")
    err = run(_shared.waypoint_validation_error("origin", {"x": 1}))
    assert err["error"].startswith("Invalid waypoint")
    assert err["received"] == {"x": 1}


def test_tool_error_envelope_does_not_allow_extra_override():
    err = _errors.tool_error(
        "failed",
        fix_hint="fix it",
        status_code=400,
        extra={"error": "override", "status_code": 500, "field": "value"},
    )
    assert err == {"error": "failed", "fix_hint": "fix it", "status_code": 400, "field": "value"}
