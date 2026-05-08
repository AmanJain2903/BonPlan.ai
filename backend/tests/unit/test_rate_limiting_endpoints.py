import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import rate_limiting, rate_limiting_admin
from app.database.models.rateLimitConfigs import Period, Scope
from app.services.rate_limiter.rate_limiter import RateLimitExceeded
from tests.conftest import FakeLimiter, FakeSessionFactory


def run(coro):
    return asyncio.run(coro)


def test_title_and_insert_formatters():
    assert rate_limiting._titlelize_optional("routes_compute_routes_pro") == "Routes Compute Routes Pro"
    assert rate_limiting_admin._format_for_insert(" Routes Pro ") == "routes_pro"
    assert rate_limiting_admin._format_for_insert("") is None


def test_validate_reset_fields_accepts_and_rejects():
    rate_limiting_admin._validate_reset_fields(Period.WEEKLY, 0, 23, 7, 12)
    with pytest.raises(HTTPException) as exc:
        rate_limiting_admin._validate_reset_fields(Period.WEEKLY, 60, 0, 1, 1)
    assert exc.value.status_code == 400
    with pytest.raises(HTTPException):
        rate_limiting_admin._validate_reset_fields(Period.WEEKLY, 0, 24, 1, 1)
    with pytest.raises(HTTPException):
        rate_limiting_admin._validate_reset_fields(Period.WEEKLY, 0, 1, 8, 1)


def test_runtime_status_consume_reset(monkeypatch):
    limiter = FakeLimiter()
    monkeypatch.setattr(rate_limiting, "get_rate_limiter", lambda: limiter)

    status = run(rate_limiting.get_rate_limit_status("dynamic_maps"))
    reset = run(rate_limiting.reset_rate_limit(rate_limiting.ResetBody(sku="dynamic_maps")))
    consumed = run(rate_limiting.consume_rate_limit(rate_limiting.ConsumeBody(sku="dynamic_maps", amount=2)))

    assert status["remaining"] == 7
    assert reset["deleted"] is True
    assert consumed["current"] == 1
    assert limiter.calls[2][2]["amount"] == 2


def test_runtime_consume_limit_exceeded(monkeypatch):
    limiter = FakeLimiter(consume=RateLimitExceeded("dynamic_maps", 1, 1, 44, "global"))
    monkeypatch.setattr(rate_limiting, "get_rate_limiter", lambda: limiter)

    with pytest.raises(HTTPException) as exc:
        run(rate_limiting.consume_rate_limit(rate_limiting.ConsumeBody(sku="dynamic_maps")))

    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"] == "44"
    assert exc.value.detail["sku"] == "Dynamic Maps"


def test_track_client_sku_clamps_count(monkeypatch):
    limiter = FakeLimiter()
    monkeypatch.setattr(rate_limiting, "get_rate_limiter", lambda: limiter)

    result = run(rate_limiting.track_client_sku(rate_limiting.TrackClientSkuBody(sku="directions", count=0)))

    assert result["status_code"] == 200
    assert limiter.calls[0][2]["amount"] == 1


def test_get_client_skus_uses_mocked_db(monkeypatch):
    config = SimpleNamespace(sku="dynamic_maps", limit=10, period=Period.MONTHLY, scope=Scope.GLOBAL)
    factory = FakeSessionFactory([config])
    monkeypatch.setattr(rate_limiting, "Session", factory)

    result = run(rate_limiting.get_client_skus())

    assert result == {"status_code": 200, "client_skus": [{"sku": "dynamic_maps", "limit": 10, "period": "monthly", "scope": "global"}]}


def test_admin_verify_rejects_non_admin(monkeypatch, user_factory, jwt_token):
    user = user_factory(is_admin=False)
    factory = FakeSessionFactory(user)
    monkeypatch.setattr(rate_limiting_admin, "Session", factory)

    with pytest.raises(HTTPException) as exc:
        run(rate_limiting_admin._verify_admin(jwt_token({"user_id": str(user.id)})))

    assert exc.value.status_code == 403


def test_admin_create_config_success(monkeypatch, jwt_token):
    limiter = FakeLimiter()
    factory = FakeSessionFactory(None)
    monkeypatch.setattr(rate_limiting_admin, "Session", factory)
    monkeypatch.setattr(rate_limiting_admin, "_verify_admin", lambda token: asyncio.sleep(0))
    monkeypatch.setattr(rate_limiting_admin, "get_rate_limiter", lambda: limiter)

    body = rate_limiting_admin.CreateRateLimitConfigBody(
        sku="Dynamic Maps",
        service="maps",
        provider="Google",
        limit=100,
        period=Period.MONTHLY,
        scope=Scope.GLOBAL,
    )
    result = run(rate_limiting_admin.create_rate_limit_config("token", body))

    assert result["status_code"] == 200
    assert factory.added[0].sku == "dynamic_maps"
    assert factory.added[0].provider == "google"
    assert factory.commit_count == 1
    assert limiter.invalidated is True


def test_admin_get_config_formats_response(monkeypatch):
    config = SimpleNamespace(
        id=uuid4(),
        sku="dynamic_maps",
        service="maps",
        description="desc",
        provider="google",
        limit=10,
        period=Period.MONTHLY,
        scope=Scope.GLOBAL,
        reset_minute=0,
        reset_hour=0,
        reset_day=1,
        reset_month=1,
    )
    monkeypatch.setattr(rate_limiting_admin, "_verify_admin", lambda token: asyncio.sleep(0))
    monkeypatch.setattr(rate_limiting_admin, "Session", FakeSessionFactory(config))

    result = run(rate_limiting_admin.get_rate_limit_config("token", sku="dynamic_maps"))

    assert result["config"]["sku"] == "Dynamic Maps"
    assert result["config"]["provider"] == "Google"


def test_admin_usage_response(monkeypatch, user_factory):
    usage = SimpleNamespace(id=uuid4(), sku="dynamic_maps", user_id=uuid4(), period_bucket="202605", usage=7, updated_at=None)
    config = SimpleNamespace(limit=10, scope=Scope.GLOBAL, period=Period.MONTHLY)
    user = user_factory(first_name="Ada", last_name="Admin")
    monkeypatch.setattr(rate_limiting_admin, "_verify_admin", lambda token: asyncio.sleep(0))
    monkeypatch.setattr(rate_limiting_admin, "Session", FakeSessionFactory([(usage, config, user)]))

    result = run(rate_limiting_admin.get_all_usage("token"))

    assert result["usage"][0]["sku"] == "Dynamic Maps"
    assert result["usage"][0]["user_name"] == "Ada Admin"
