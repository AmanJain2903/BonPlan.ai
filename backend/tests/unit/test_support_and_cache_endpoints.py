import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.agent.api.v1.endpoints import api_cache as agent_cache
from app.api.v1.endpoints import api_cache, support
from app.database.models.apiCacheTable import ApiCache
from app.database.models.faqTable import FAQ
from app.database.models.supportTicketsTable import TicketStatus
from tests.conftest import FakeSessionFactory


def run(coro):
    return asyncio.run(coro)


def test_api_cache_insert_replaces_existing(monkeypatch):
    existing = ApiCache(cache_key="k", cache_value={"old": True})
    factory = FakeSessionFactory(existing)
    monkeypatch.setattr(api_cache, "Session", factory)

    result = run(api_cache.insert_api_cache(api_cache.ApiCacheInsertBody(cache_key="k", cache_value={"new": True})))

    assert result["status_code"] == 200
    assert factory.deleted == [existing]
    assert factory.added[0].cache_value == {"new": True}
    assert factory.commit_count == 1


def test_api_cache_insert_validates_body():
    with pytest.raises(HTTPException) as exc:
        run(api_cache.insert_api_cache(api_cache.ApiCacheInsertBody(cache_key="", cache_value={})))
    assert exc.value.status_code == 400


def test_api_cache_retrieve_found_and_expired(monkeypatch):
    fresh = ApiCache(cache_key="fresh", cache_value={"ok": True})
    fresh.created_at = datetime.now(timezone.utc)
    expired = ApiCache(cache_key="old", cache_value={"ok": False})
    expired.created_at = datetime.now(timezone.utc) - timedelta(days=3)
    factory = FakeSessionFactory(fresh, expired, None)
    monkeypatch.setattr(api_cache, "Session", factory)

    found = run(api_cache.retrieve_api_cache("fresh", expires_in=1))
    old = run(api_cache.retrieve_api_cache("old", expires_in=1))
    missing = run(api_cache.retrieve_api_cache("missing", expires_in=1))

    assert found["cache_value"] == {"ok": True}
    assert old["status_code"] == 404
    assert missing["status_code"] == 404
    assert expired in factory.deleted


def test_agent_api_cache_uses_same_contract(monkeypatch):
    cache = ApiCache(cache_key="agent", cache_value={"a": 1})
    cache.created_at = datetime.now(timezone.utc)
    factory = FakeSessionFactory(cache)
    monkeypatch.setattr(agent_cache, "Session", factory)

    result = run(agent_cache.retrieve_api_cache("agent", expires_in=1))

    assert result["status_code"] == 200
    assert result["cache_value"] == {"a": 1}


def test_support_decode_token_and_submit_ticket(monkeypatch, user_factory, jwt_token):
    user = user_factory(id=uuid4(), email="user@example.test")
    factory = FakeSessionFactory(user)
    sent = []
    monkeypatch.setattr(support, "Session", factory)
    monkeypatch.setattr(support, "send_email", lambda **kwargs: asyncio.sleep(0, result=sent.append(kwargs)))
    token = jwt_token({"user_id": str(user.id)})

    result = run(support.submit_ticket(support.SubmitTicketBody(token=token, subject=" Help ", body=" Body ")))

    assert result["status_code"] == 200
    assert factory.added[0].subject == "Help"
    assert factory.added[0].body == "Body"
    assert sent[0]["to_email"] == support.settings.SENDER_EMAIL


def test_support_admin_faq_crud(monkeypatch):
    faq = FAQ(question="Q", answer="A", order=2, is_published=False)
    faq.id = uuid4()
    faq.created_at = datetime.now(timezone.utc)
    faq.updated_at = datetime.now(timezone.utc)
    factory = FakeSessionFactory([faq], faq, faq, faq)
    monkeypatch.setattr(support, "Session", factory)
    monkeypatch.setattr(support, "_verify_admin", lambda token: asyncio.sleep(0, result="admin"))

    listed = run(support.admin_get_faqs("token"))
    created = run(support.admin_create_faq(support.CreateFAQBody(token="token", question="New", answer="Answer")))
    updated = run(support.admin_update_faq(str(faq.id), support.UpdateFAQBody(token="token", question=" Changed ", is_published=True)))
    deleted = run(support.admin_delete_faq(str(faq.id), "token"))

    assert listed["faqs"][0]["question"] == "Q"
    assert created["status_code"] == 200
    assert updated["status_code"] == 200
    assert faq.question == "Changed"
    assert faq.is_published is True
    assert deleted["status_code"] == 200


def test_support_ticket_status_and_acknowledge(monkeypatch):
    ticket = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        user_email="user@example.test",
        subject="Trip broken",
        body="details",
        status=TicketStatus.OPEN,
        acknowledged=False,
        created_at=None,
        updated_at=None,
    )
    factory = FakeSessionFactory(ticket, ticket, ticket)
    sent = []
    monkeypatch.setattr(support, "Session", factory)
    monkeypatch.setattr(support, "_verify_admin", lambda token: asyncio.sleep(0, result="admin"))
    monkeypatch.setattr(support, "send_email", lambda **kwargs: asyncio.sleep(0, result=sent.append(kwargs)))

    status = run(support.admin_update_ticket_status(str(ticket.id), support.UpdateTicketStatusBody(token="token", status=TicketStatus.RESOLVED)))
    ack = run(support.admin_acknowledge_ticket(str(ticket.id), "token"))
    reply = run(support.admin_reply_to_ticket(str(ticket.id), support.ReplyToTicketBody(token="token", message="Done")))

    assert status["status_code"] == 200
    assert ack["status_code"] == 200
    assert reply["status_code"] == 200
    assert ticket.status == TicketStatus.RESOLVED
    assert ticket.acknowledged is True
    assert len(sent) == 3


def test_support_acknowledge_conflict(monkeypatch):
    ticket = SimpleNamespace(id=uuid4(), acknowledged=True)
    monkeypatch.setattr(support, "Session", FakeSessionFactory(ticket))
    monkeypatch.setattr(support, "_verify_admin", lambda token: asyncio.sleep(0, result="admin"))

    with pytest.raises(HTTPException) as exc:
        run(support.admin_acknowledge_ticket(str(ticket.id), "token"))

    assert exc.value.status_code == 409


def test_get_published_faqs(monkeypatch):
    faq = FAQ(question="Q", answer="A", order=1)
    faq.id = uuid4()
    monkeypatch.setattr(support, "Session", FakeSessionFactory([faq]))

    result = run(support.get_published_faqs())

    assert result == {"faqs": [{"id": str(faq.id), "question": "Q", "answer": "A", "order": 1}]}
