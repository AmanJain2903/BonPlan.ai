import asyncio
from types import SimpleNamespace

from redis.exceptions import RedisError

from app.agent.api import caching as agent_caching
from app.agent.helpers import qa_persistence
from app.api import caching
from app.core import redis_client
from app.services import trip_lifecycle
from app.services.rate_limiter import usage_cleanup
from app.database.models.rateLimitConfigs import Period
from app.utils import emailVerification, http
from tests.conftest import FakeExecuteResult, FakeSessionFactory


def run(coro):
    return asyncio.run(coro)


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.payload = payload or {}

    def json(self):
        return self.payload


class FakeHttpClient:
    def __init__(self, get_response=None, fail=False):
        self.get_response = get_response or FakeResponse(200, {"status_code": 200, "cache_value": {"hit": True}})
        self.fail = fail
        self.posts = []
        self.gets = []
        self.is_closed = False

    async def get(self, url, **kwargs):
        self.gets.append((url, kwargs))
        if self.fail:
            raise RuntimeError("network blocked")
        return self.get_response

    async def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        if self.fail:
            raise RuntimeError("network blocked")
        return FakeResponse(200, {})

    async def aclose(self):
        self.is_closed = True


def test_api_caching_helpers_use_shared_http_client(monkeypatch):
    client = FakeHttpClient()
    monkeypatch.setattr(caching, "get_http_client", lambda: client)

    key_a = run(caching.generate_cache_key("places", {"b": 2, "a": 1}))
    key_b = run(caching.generate_cache_key("places", {"a": 1, "b": 2}))
    value = run(caching.retrieve_api_cache("key", expires_in=3))
    run(caching.insert_api_cache("key", {"x": 1}))

    assert key_a == key_b
    assert value == {"hit": True}
    assert client.gets[0][1]["params"] == {"cache_key": "key", "expires_in": 3}
    assert client.posts[0][1]["json"] == {"cache_key": "key", "cache_value": {"x": 1}}


def test_agent_api_caching_misses_and_errors(monkeypatch):
    miss_client = FakeHttpClient(FakeResponse(200, {"status_code": 404}))
    monkeypatch.setattr(agent_caching, "get_http_client", lambda: miss_client)
    assert run(agent_caching.retrieve_api_cache("key")) is None

    failing = FakeHttpClient(fail=True)
    monkeypatch.setattr(agent_caching, "get_http_client", lambda: failing)
    assert run(agent_caching.retrieve_api_cache("key")) is None
    run(agent_caching.insert_api_cache("key", {"x": 1}))


def test_process_wide_http_client_lifecycle(monkeypatch):
    fake = FakeHttpClient()
    monkeypatch.setattr(http.httpx, "AsyncClient", lambda timeout: fake)
    http._client = None

    assert http.get_http_client() is fake
    assert http.get_http_client() is fake
    run(http.close_http_client())

    assert fake.is_closed is True
    assert http._client is None


def test_redis_client_ping_and_close(monkeypatch):
    class FakePool:
        def __init__(self):
            self.disconnected = False

        async def disconnect(self, inuse_connections=True):
            self.disconnected = inuse_connections

    class FakeRedis:
        def __init__(self, connection_pool):
            self.connection_pool = connection_pool
            self.closed = False

        async def ping(self):
            return True

        async def aclose(self):
            self.closed = True

    pool = FakePool()
    monkeypatch.setattr(redis_client, "_build_pool", lambda: pool)
    monkeypatch.setattr(redis_client.redis, "Redis", FakeRedis)
    redis_client._pool = None
    redis_client._client = None

    client = redis_client.get_redis()
    assert redis_client.get_redis() is client
    assert run(redis_client.ping_redis()) is True
    run(redis_client.close_redis())
    assert client.closed is True
    assert pool.disconnected is True


def test_redis_ping_failure(monkeypatch):
    class BadRedis:
        async def ping(self):
            raise RedisError("down")

    monkeypatch.setattr(redis_client, "get_redis", lambda: BadRedis())
    assert run(redis_client.ping_redis()) is False


def test_send_email_uses_smtp_without_real_network(monkeypatch, tmp_path):
    calls = []

    class FakeSMTP:
        def __init__(self, host, port):
            calls.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def login(self, email, password):
            calls.append(("login", email, password))

        def sendmail(self, from_email, to_email, body):
            calls.append(("sendmail", from_email, to_email, "Subject: Subject" in body))

    async def immediate(func):
        return func()

    monkeypatch.setattr(emailVerification.smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(emailVerification.asyncio, "to_thread", immediate)
    run(emailVerification.send_email("to@example.test", "Subject", "<p>Body</p>"))

    assert calls[0] == ("connect", "smtp.gmail.com", 465)
    assert calls[-1][0] == "sendmail"


def test_usage_cleanup_thresholds_and_db_delete(monkeypatch):
    assert usage_cleanup._get_threshold_bucket(Period.DAILY, usage_cleanup.ZoneInfo("UTC")).isdigit()

    factory = FakeSessionFactory(
        FakeExecuteResult(rowcount=1),
        FakeExecuteResult(rowcount=2),
        FakeExecuteResult(rowcount=3),
        FakeExecuteResult(rowcount=4),
    )
    monkeypatch.setattr(usage_cleanup, "Session", factory)

    run(usage_cleanup.cleanup_old_usage())

    assert factory.commit_count == 1
    assert len(factory.executed) == 4


def test_trip_lifecycle_update_executes_three_statements(monkeypatch):
    factory = FakeSessionFactory(
        FakeExecuteResult(rowcount=1),
        FakeExecuteResult(rowcount=2),
        FakeExecuteResult(rowcount=3),
    )
    monkeypatch.setattr(trip_lifecycle, "Session", factory)
    monkeypatch.setattr(trip_lifecycle, "_now_utc_ts", lambda: 123)

    run(trip_lifecycle.run_trip_lifecycle_update())

    assert factory.commit_count == 1
    assert [r.rowcount for r in [FakeExecuteResult(rowcount=1), FakeExecuteResult(rowcount=2), FakeExecuteResult(rowcount=3)]]
    assert len(factory.executed) == 3


def test_qa_persistence_insert_update_load_and_fire(monkeypatch):
    entry = {"context": "seed", "answer": "A"}
    factory = FakeSessionFactory(None)
    monkeypatch.setattr(qa_persistence, "Session", factory)
    run(qa_persistence.persist_qa_entry("trip", "user", entry))
    assert factory.added[0].qa_pairs == [entry]
    assert factory.commit_count == 1

    row = SimpleNamespace(qa_pairs=[{"context": "seed", "answer": "old"}, {"context": "day_1", "answer": "B"}])
    factory = FakeSessionFactory(row, row)
    monkeypatch.setattr(qa_persistence, "Session", factory)
    run(qa_persistence.persist_qa_entry("trip", "user", entry))
    loaded = run(qa_persistence.load_collab_qa("trip", "user"))
    assert row.qa_pairs == [{"context": "day_1", "answer": "B"}, entry]
    assert loaded == row.qa_pairs

    created = []
    monkeypatch.setattr(qa_persistence.asyncio, "create_task", lambda coro: (created.append(coro), coro.close())[0])
    qa_persistence.fire_persist_qa("trip", "user", entry)
    assert len(created) == 1
