import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import auth
from app.core.config import settings
from tests.conftest import FakeSessionFactory


def run(coro):
    return asyncio.run(coro)


def test_auth_validation_helpers():
    assert auth.is_valid_email("person@example.com")
    assert not auth.is_valid_email("missing-at")
    assert auth.is_valid_password("Strong1!")
    assert not auth.is_valid_password("weak")
    assert auth.makeFirstLetterCapital("aman") == "Aman"


def test_hash_and_check_password_round_trip():
    password_hash = run(auth._hash_password("Strong1!"))
    assert password_hash != "Strong1!"
    assert run(auth._check_password("Strong1!", password_hash)) is True
    assert run(auth._check_password("Wrong1!", password_hash)) is False


def test_local_login_success_uses_mocked_session(monkeypatch, user_factory):
    user = user_factory(is_new_user=True, password_hash="hash")
    factory = FakeSessionFactory(user)
    monkeypatch.setattr(auth, "Session", factory)
    monkeypatch.setattr(auth, "_check_password", lambda password, password_hash: asyncio.sleep(0, result=True))

    result = run(auth.local_login("aman@example.test", "Strong1!"))

    assert result["status_code"] == 200
    assert result["email"] == "aman@example.test"
    assert result["is_new_user"] is True
    assert user.is_new_user is False
    assert factory.commit_count == 1
    decoded = jwt.decode(result["token"], settings.SECRET_KEY, algorithms=["HS256"])
    assert decoded["user_id"] == str(user.id)


def test_local_login_rejects_unverified_user_and_sends_email(monkeypatch, user_factory):
    user = user_factory(is_verified=False, password_hash="hash")
    factory = FakeSessionFactory(user)
    sent = []
    monkeypatch.setattr(auth, "Session", factory)
    monkeypatch.setattr(auth, "_check_password", lambda password, password_hash: asyncio.sleep(0, result=True))
    monkeypatch.setattr(auth, "_send_verification_email_for_user", lambda email, db: asyncio.sleep(0, result=sent.append(email)))

    with pytest.raises(HTTPException) as exc:
        run(auth.local_login("aman@example.test", "Strong1!"))

    assert exc.value.status_code == 403
    assert sent == ["aman@example.test"]


def test_verify_email_sets_verified(monkeypatch, user_factory):
    user = user_factory(is_verified=False)
    factory = FakeSessionFactory(user)
    monkeypatch.setattr(auth, "Session", factory)
    token = jwt.encode(
        {"email": user.email, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        settings.SECRET_KEY,
        algorithm="HS256",
    )

    result = run(auth.verify_email(token))

    assert result == {"message": "Email verified successfully", "status_code": 200}
    assert user.is_verified is True
    assert factory.commit_count == 1


def test_reset_password_rejects_wrong_purpose(jwt_token):
    token = jwt_token({"email": "aman@example.test", "purpose": "verify"})

    with pytest.raises(HTTPException) as exc:
        run(auth.reset_password(token, "Strong1!"))

    assert exc.value.status_code == 400


def test_update_profile_updates_mock_user(monkeypatch, user_factory, jwt_token):
    user = user_factory(first_name="Old", last_name="Name")
    factory = FakeSessionFactory(user)
    monkeypatch.setattr(auth, "Session", factory)
    req = auth.UpdateProfileRequest(
        token=jwt_token({"user_id": str(user.id)}),
        first_name=" new ",
        last_name=" person ",
        country_code=" +91 ",
        phone=" 999 ",
        preferences={"activity_interests": ["food"]},
    )

    result = run(auth.update_profile(req))

    assert result["status_code"] == 200
    assert user.first_name == "New"
    assert user.last_name == "Person"
    assert user.phone == {"country_code": "+91", "number": "999"}
    assert user.preferences == {"activity_interests": ["food"]}


def test_google_login_existing_google_user(monkeypatch, user_factory):
    user = user_factory(auth_provider="google", is_new_user=True)
    factory = FakeSessionFactory(user)
    monkeypatch.setattr(auth, "Session", factory)
    monkeypatch.setattr(
        auth.id_token,
        "verify_oauth2_token",
        lambda token, request, audience: {"email": user.email, "given_name": "Aman", "family_name": "Tester"},
    )

    result = run(auth.google_login("google-token"))

    assert result["status_code"] == 200
    assert user.is_new_user is False
    assert factory.commit_count == 1


def test_delete_user_removes_mock_user(monkeypatch, user_factory, jwt_token):
    user = user_factory(id=uuid4())
    factory = FakeSessionFactory(user)
    monkeypatch.setattr(auth, "Session", factory)

    result = run(auth.delete_user(jwt_token({"user_id": str(user.id)})))

    assert result["status_code"] == 200
    assert factory.deleted == [user]
    assert factory.commit_count == 1
