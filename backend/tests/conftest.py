import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

# Keep imports deterministic and safe before app.core.config.Settings is created.
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-secret")
os.environ.setdefault("GOOGLE_MAPS_API_KEY", "test-google-maps")
os.environ.setdefault("SERPER_API_KEY", "test-serper")
os.environ.setdefault("RAPID_API_KEY", "test-rapid")
os.environ.setdefault("RESEND_API_KEY", "test-resend")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("POSTGRES_SERVER", "127.0.0.1")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "bonplan_test")
os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/15")

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


class FakeScalarResult:
    def __init__(self, rows):
        if rows is None:
            rows = []
        if not isinstance(rows, list):
            rows = [rows]
        self.rows = rows

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None

    def scalar_one_or_none(self):
        return self.rows[0] if self.rows else None


class FakeExecuteResult:
    def __init__(self, rows=None, rowcount=0):
        self.rows = [] if rows is None else (rows if isinstance(rows, list) else [rows])
        self.rowcount = rowcount

    def scalars(self):
        return FakeScalarResult(self.rows)

    def scalar_one_or_none(self):
        return self.scalars().scalar_one_or_none()

    def all(self):
        return self.rows


class FakeAsyncSession:
    def __init__(self, factory):
        self.factory = factory
        self.added = factory.added
        self.deleted = factory.deleted
        self.executed = factory.executed
        self.commits = factory.commits
        self.rollbacks = factory.rollbacks

    async def __aenter__(self):
        self.factory.sessions.append(self)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def execute(self, stmt):
        self.executed.append(stmt)
        if not self.factory.results:
            return FakeExecuteResult([])
        result = self.factory.results.pop(0)
        if callable(result):
            result = result(stmt)
        if isinstance(result, FakeExecuteResult):
            return result
        return FakeExecuteResult(result)

    def add(self, obj):
        self.added.append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)

    async def commit(self):
        self.factory.commit_count += 1
        self.commits.append(datetime.now(timezone.utc))

    async def rollback(self):
        self.factory.rollback_count += 1
        self.rollbacks.append(datetime.now(timezone.utc))

    async def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()
        self.factory.refreshed.append(obj)

    async def flush(self):
        return None


class FakeSessionFactory:
    def __init__(self, *results):
        self.results = list(results)
        self.sessions = []
        self.added = []
        self.deleted = []
        self.executed = []
        self.commits = []
        self.rollbacks = []
        self.refreshed = []
        self.commit_count = 0
        self.rollback_count = 0

    def __call__(self):
        return FakeAsyncSession(self)

    def push(self, *results):
        self.results.extend(results)
        return self


class FakeLimiter:
    def __init__(self, *, status=None, consume=None, deleted=True):
        self.status = status
        self.consume_result = consume
        self.deleted = deleted
        self.calls = []
        self.invalidated = False

    async def get_status(self, sku, user_id=None):
        self.calls.append(("get_status", sku, user_id))
        return self.status or SimpleNamespace(
            sku=sku,
            scope="global",
            period="monthly",
            limit=10,
            current=3,
            remaining=7,
            allowed=True,
            retry_after_seconds=0,
            skipped=False,
        )

    async def consume(self, sku, **kwargs):
        self.calls.append(("consume", sku, kwargs))
        if isinstance(self.consume_result, Exception):
            raise self.consume_result
        return self.consume_result or SimpleNamespace(
            sku=sku,
            allowed=True,
            current=1,
            remaining=9,
            retry_after_seconds=0,
            skipped=False,
        )

    async def reset(self, sku, user_id=None):
        self.calls.append(("reset", sku, user_id))
        return self.deleted

    async def invalidate_config_cache(self):
        self.invalidated = True


@pytest.fixture
def fake_session_factory():
    return FakeSessionFactory


@pytest.fixture
def jwt_token():
    import jwt
    from app.core.config import settings

    def make(payload):
        return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")

    return make


@pytest.fixture
def user_factory():
    def make(**overrides):
        base = dict(
            id=uuid4(),
            first_name="Aman",
            last_name="Tester",
            email="aman@example.test",
            phone={"country_code": "+1", "number": "5551234567"},
            password_hash="$2b$12$test",
            auth_provider="local",
            is_verified=True,
            is_new_user=True,
            is_admin=False,
            preferences={"pace": "balanced"},
        )
        base.update(overrides)
        return SimpleNamespace(**base)

    return make
