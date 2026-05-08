import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import plan
from app.core.config import settings
from app.database.models.tripMembersTable import TripInvitationStatus, TripRole
from tests.conftest import FakeSessionFactory


def run(coro):
    return asyncio.run(coro)


def test_plan_helper_formatting_and_validation(user_factory):
    assert plan._is_valid_email("USER@example.com") is True
    assert plan._is_valid_email("bad") is False
    assert plan._normalize_email(" USER@example.COM ") == "user@example.com"
    raw, hashed = plan._new_invitation_token()
    assert raw and hashed == plan._hash_invitation_token(raw)
    assert plan._role_value(TripRole.OWNER) == "owner"
    assert plan._can_share("owner") is True
    assert plan._can_share("shared_viewer") is False

    user = user_factory(first_name="Ada", last_name="Lovelace")
    assert plan._user_response(user) == {"first_name": "Ada", "last_name": "Lovelace", "email": "aman@example.test"}
    assert plan._user_response(None, "x@example.test") == {"first_name": "", "last_name": "", "email": "x@example.test"}


def test_plan_time_helpers_from_json_dates():
    data = {"year": 2026, "month": 5, "day": 8, "timezoneId": "UTC"}
    assert plan.get_utc_datetime(data) == ("2026-05-08T00:00:00Z", 1778198400)
    assert plan.get_local_time_string(data) == "2026-05-08T00:00:00"
    assert plan.get_local_time_string(data, isEndTime=True) == "2026-05-08T23:59:00"


def test_decode_user_id_rejects_invalid_token():
    with pytest.raises(HTTPException) as exc:
        run(plan._decode_user_id("not-a-token"))
    assert exc.value.status_code == 401


def test_decode_user_id_success(jwt_token):
    user_id = uuid4()
    assert run(plan._decode_user_id(jwt_token({"user_id": str(user_id)}))) == user_id


def test_load_user_or_404_success_and_missing(user_factory):
    user = user_factory()
    factory = FakeSessionFactory(user)
    session = factory()
    assert run(plan._load_user_or_404(session, user.id)) == user

    missing = FakeSessionFactory(None)()
    with pytest.raises(HTTPException) as exc:
        run(plan._load_user_or_404(missing, uuid4()))
    assert exc.value.status_code == 404


def test_member_response_shapes(user_factory):
    member_id = uuid4()
    owner_id = uuid4()
    member = SimpleNamespace(
        id=member_id,
        trip_id=uuid4(),
        user_id=owner_id,
        invited_email=None,
        role=TripRole.OWNER,
        invitation_status=TripInvitationStatus.ACCEPTED.value,
        accepted_at=None,
        expires_at=None,
        created_at=None,
        updated_at=None,
        user=user_factory(id=owner_id),
    )

    response = plan._member_response(member, owner_id=owner_id)

    assert response["id"] == member_id
    assert response["role"] == "owner"
    assert response["is_owner"] is True
    assert response["email"] == "aman@example.test"
