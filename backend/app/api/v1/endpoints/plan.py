# backend/app/api/v1/endpoints/plan.py

"""
This file contains the plan endpoints for the v1 version of the API.
"""

import hashlib
import html
import jwt
import re
import secrets
import uuid

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, APIRouter
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select, func as sa_func

from app.core.config import settings
from app.data.labels import paceLabels, budgetLabels
from app.database.database import Session
from app.database.models.tripsTable import Trip, PlanningType, RoutingStyle, PlanStatus
from app.database.models.tripItinerariesTable import TripItinerary
from app.database.models.usersTable import User
from app.database.models.tripMembersTable import TripMember, TripRole, TripInvitationStatus
from app.logging import get_api_logger
from app.utils.emailVerification import BONPLAN_LOGO_CID, BONPLAN_LOGO_PATH, send_email

logger = get_api_logger("api.plan")

router = APIRouter()


class ShareTripRequest(BaseModel):
    email: str
    role: str


class CreateShareLinkRequest(BaseModel):
    role: str = TripRole.SHARED_VIEWER.value


def _is_valid_email(email: str) -> bool:
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email or ""))


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _hash_invitation_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_invitation_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, _hash_invitation_token(token)


def _role_value(role) -> str:
    return role.value if hasattr(role, "value") else str(role)


def _user_response(user: User | None, fallback_email: str | None = None) -> dict:
    return {
        "first_name": user.first_name if user else "",
        "last_name": user.last_name if user else "",
        "email": user.email if user else (fallback_email or ""),
    }


def _member_response(member: TripMember, owner_id=None) -> dict:
    accepted = member.invitation_status == TripInvitationStatus.ACCEPTED.value
    email = member.user.email if member.user else member.invited_email
    return {
        "id": member.id,
        "user_id": member.user_id,
        "role": _role_value(member.role),
        "invitation_status": member.invitation_status,
        "accepted": accepted,
        "first_name": member.user.first_name if member.user else "",
        "last_name": member.user.last_name if member.user else "",
        "email": email or "",
        "is_owner": owner_id is not None and member.user_id == owner_id,
        "created_at": member.created_at,
        "updated_at": member.updated_at,
    }


def _format_invitation_email(
    *,
    recipient_name: str,
    inviter_name: str,
    trip_title: str,
    role_label: str,
    accept_link: str,
) -> str:
    recipient_name = html.escape(recipient_name)
    inviter_name = html.escape(inviter_name)
    trip_title = html.escape(trip_title)
    role_label = html.escape(role_label)
    accept_link = html.escape(accept_link, quote=True)
    logo_src = html.escape(f"cid:{BONPLAN_LOGO_CID}", quote=True)
    return f"""
    <div style="margin:0;padding:0;background:#0B0C10;color:#C5C6C7;font-family:Inter,Arial,sans-serif;">
      <div style="max-width:640px;margin:0 auto;padding:32px 20px;">
        <div style="border:1px solid rgba(255,255,255,0.1);border-radius:18px;background:#1F2833;padding:28px;">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:18px;">
            <img src="{logo_src}" alt="BonPlan.ai" width="36" height="36" style="display:block;border-radius:10px;" />
            <div style="font-size:22px;font-weight:800;color:#ffffff;">BonPlan<span style="color:#66FCF1;">.</span>ai</div>
          </div>
          <p style="font-size:16px;line-height:1.6;margin:0 0 14px;">Hello {recipient_name},</p>
          <p style="font-size:16px;line-height:1.6;margin:0 0 18px;">
            {inviter_name} shared the itinerary <strong style="color:#ffffff;">{trip_title}</strong> with you.
          </p>
          <div style="border:1px solid rgba(102,252,241,0.24);border-radius:14px;background:rgba(102,252,241,0.06);padding:16px;margin:22px 0;">
            <div style="font-size:12px;letter-spacing:0.12em;text-transform:uppercase;color:#66FCF1;font-weight:700;margin-bottom:6px;">Access</div>
            <div style="font-size:18px;color:#ffffff;font-weight:700;">{role_label}</div>
          </div>
          <a href="{accept_link}" style="display:inline-block;background:#66FCF1;color:#0B0C10;text-decoration:none;font-weight:800;border-radius:12px;padding:13px 18px;margin:4px 0 18px;">
            Accept Invitation
          </a>
          <p style="font-size:13px;line-height:1.5;color:rgba(197,198,199,0.72);margin:0;">
            If you are not logged in, BonPlan.ai will ask you to log in or create an account before opening the itinerary.
          </p>
        </div>
      </div>
    </div>
    """


def _format_edit_access_request_email(
    *,
    owner_name: str,
    requester_name: str,
    requester_email: str,
    trip_title: str,
    elevate_link: str,
) -> str:
    owner_name = html.escape(owner_name)
    requester_name = html.escape(requester_name)
    requester_email = html.escape(requester_email)
    trip_title = html.escape(trip_title)
    elevate_link = html.escape(elevate_link, quote=True)
    logo_src = html.escape(f"cid:{BONPLAN_LOGO_CID}", quote=True)
    return f"""
    <div style="margin:0;padding:0;background:#0B0C10;color:#C5C6C7;font-family:Inter,Arial,sans-serif;">
      <div style="max-width:640px;margin:0 auto;padding:32px 20px;">
        <div style="border:1px solid rgba(255,255,255,0.1);border-radius:18px;background:#1F2833;padding:28px;">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:18px;">
            <img src="{logo_src}" alt="BonPlan.ai" width="36" height="36" style="display:block;border-radius:10px;" />
            <div style="font-size:22px;font-weight:800;color:#ffffff;">BonPlan<span style="color:#66FCF1;">.</span>ai</div>
          </div>
          <p style="font-size:16px;line-height:1.6;margin:0 0 14px;">Hello {owner_name},</p>
          <p style="font-size:16px;line-height:1.6;margin:0 0 18px;">
            {requester_name} ({requester_email}) requested editing access to <strong style="color:#ffffff;">{trip_title}</strong>.
          </p>
          <a href="{elevate_link}" style="display:inline-block;background:#66FCF1;color:#0B0C10;text-decoration:none;font-weight:800;border-radius:12px;padding:13px 18px;margin:4px 0 18px;">
            Elevate Access
          </a>
          <p style="font-size:13px;line-height:1.5;color:rgba(197,198,199,0.72);margin:0;">
            This will upgrade the requester from viewer to editor for this itinerary.
          </p>
        </div>
      </div>
    </div>
    """


def _coerce_uuid(value, field_name: str = "id") -> uuid.UUID:
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}.")


async def _decode_user_id(token: str) -> uuid.UUID:
    if not token:
        raise HTTPException(status_code=400, detail="Token is required.")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session. Please log in again.")
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid token.")
    return _coerce_uuid(user_id, "token")


async def _load_user_or_404(db, user_id: uuid.UUID) -> User:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user


async def _get_accepted_member(db, trip_id: str, user_id: uuid.UUID) -> TripMember | None:
    return (await db.execute(
        select(TripMember).where(
            TripMember.trip_id == trip_id,
            TripMember.user_id == user_id,
            TripMember.invitation_status == TripInvitationStatus.ACCEPTED.value,
        )
    )).scalar_one_or_none()


def _can_share(role: str) -> bool:
    return role in {TripRole.OWNER.value, TripRole.SHARED_EDITOR.value}

def get_utc_datetime(data):
    local_tz = ZoneInfo(data["timezoneId"])
    local_dt = datetime(
        year=data["year"], 
        month=data["month"], 
        day=data["day"], 
        hour=0, 
        minute=0, 
        second=0, 
        tzinfo=local_tz
    )
    utc_tz = ZoneInfo("UTC")
    utc_dt = local_dt.astimezone(utc_tz)
    utc_time_string = utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    utc_timestamp = int(utc_dt.timestamp())
    return utc_time_string, utc_timestamp

def get_local_time_string(data, isEndTime: bool = False):
    local_dt = datetime(
        year=data["year"], 
        month=data["month"], 
        day=data["day"], 
        hour=23 if isEndTime else 0, 
        minute=59 if isEndTime else 0, 
        second=0
    )
    local_time_string = local_dt.strftime("%Y-%m-%dT%H:%M:%S")
    return local_time_string

"""
Draft a plan endpoint
"""
@router.post("/draft-plan", response_model=dict)
async def draft_plan(token: str, data: dict):
    if not token or not data:
        raise HTTPException(status_code=400, detail="All fields are required.")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session. Please log in again.")
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid token.")

    async with Session() as db:
        try:
            user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=404, detail="User not found.")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to draft plan: {e}")

        try:
            planningType = data.get("planningStyle")
            routingStyle = data.get("routingStyle")
            tripData = data.get("tripData")
            if not tripData:
                raise HTTPException(status_code=400, detail="Trip data is required.")
            origin = tripData.get("origin")
            destinations = tripData.get("destinations")
            startDate = tripData.get("startDate")
            startDate_utc_time_string, startDate_utc_timestamp = get_utc_datetime(startDate)
            startDate_local_time_string = get_local_time_string(startDate)
            startDate["utcTimeString"] = startDate_utc_time_string
            startDate["utcTimestamp"] = startDate_utc_timestamp
            startDate["localTimeString"] = startDate_local_time_string
            endDate = tripData.get("endDate")
            endDate_utc_time_string, endDate_utc_timestamp = get_utc_datetime(endDate)
            endDate_local_time_string = get_local_time_string(endDate, isEndTime=True)
            endDate["utcTimeString"] = endDate_utc_time_string
            endDate["utcTimestamp"] = endDate_utc_timestamp
            endDate["localTimeString"] = endDate_local_time_string
            pace = tripData.get("pace")
            budget = tripData.get("budget")
            adults = tripData.get("adults")
            children = tripData.get("children")
            preferences = tripData.get("preferences")

            if origin is None or destinations is None or startDate is None or endDate is None or pace is None or budget is None or adults is None or children is None:
                raise HTTPException(status_code=400, detail="All fields are required.")

            newTrip = Trip(
                owner_id=user_id,
                planning_type=PlanningType(planningType),
                routing_style=RoutingStyle(routingStyle),
                origin=origin,
                destinations=destinations,
                start_date=startDate,
                end_date=endDate,
                pace=paceLabels[pace],
                budget=budgetLabels[budget],
                adults=adults,
                children=children,
                status=PlanStatus.DRAFT,
            )
            db.add(newTrip)
            await db.flush()

            newTripMember = TripMember(
                trip_id=newTrip.id,
                user_id=user_id,
                role=TripRole.OWNER,
                invitation_status=TripInvitationStatus.ACCEPTED.value,
                accepted_at=datetime.now(timezone.utc),
                trip_preferences=preferences,
            )
            db.add(newTripMember)
            await db.flush()

            if len(destinations) > 1:
                tripTitle = f"{origin.get('city', 'Origin')} to {destinations[0].get('city', 'Destination')} and {len(destinations) - 1} others"
            else:
                tripTitle = f"{origin.get('city', 'Origin')} to {destinations[0].get('city', 'Destination')}"

            newTripItinerary = TripItinerary(
                trip_id=newTrip.id,
                title=tripTitle,
                origin=origin.get("city", "Origin"),
                destinations=[d.get("city", "Destination") for d in destinations],
                start_date=startDate,
                end_date=endDate
            )
            db.add(newTripItinerary)

            await db.commit()
            await db.refresh(newTripItinerary)

            return {"message": "Plan drafted successfully.", "status_code": 201, "trip_id": newTrip.id}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            logger.exception("Failed to draft plan", error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to draft plan: {e}")

"""
Get RBAC of a user for a plan by id endpoint
"""
@router.get("/rbac/{id}", response_model=dict)
async def get_rbac_for_plan(token: str, id: str):
    if not token:
        raise HTTPException(status_code=400, detail="Token is required.")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session. Please log in again.")
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid token.")

    async with Session() as db:
        try:
            user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=404, detail="User not found.")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get RBAC for trip: {e}")

        try:
            trip = (await db.execute(select(Trip).where(Trip.id == id))).scalar_one_or_none()
            if not trip:
                return {"message": "Trip not found.", "status_code": 404, "rbac": None}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get RBAC for trip: {e}")

        try:
            rbac = (await db.execute(
                select(TripMember).where(
                    TripMember.trip_id == id,
                    TripMember.user_id == user_id,
                    TripMember.invitation_status == TripInvitationStatus.ACCEPTED.value,
                )
            )).scalar_one_or_none()
            if not rbac:
                return {"message": "You lack this access.", "status_code": 403, "rbac": None}
        except Exception as e:
            logger.error("Failed to get RBAC for trip", trip_id=id, user_id=user_id, error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to get RBAC for draft plan: {e}")

        return {"message": "RBAC fetched successfully.", "status_code": 200, "rbac": rbac.role}

"""
Get all plans for a user with RBAC endpoint
"""
@router.get("/plans", response_model=dict)
async def get_plans(token: str):
    if not token:
        raise HTTPException(status_code=400, detail="Token is required.")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session. Please log in again.")
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid token.")

    async with Session() as db:
        try:
            user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=404, detail="User not found.")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get plans: {e}")

        try:
            memberships = (await db.execute(
                select(TripMember).where(
                    TripMember.user_id == user_id,
                    TripMember.invitation_status == TripInvitationStatus.ACCEPTED.value,
                )
            )).scalars().all()
            if not memberships:
                return {"message": "You have no plans yet.", "status_code": 404, "plans": None}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get memberships: {e}")

        try:
            plan_ids = [m.trip_id for m in memberships]
            plans = (await db.execute(
                select(Trip).where(Trip.id.in_(plan_ids)).order_by(Trip.updated_at.desc())
            )).scalars().all()
            if not plans:
                return {"message": "You have no plans yet.", "status_code": 404, "plans": None}
        except Exception as e:
            logger.error("Failed to get plans", user_id=user_id, error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to get plans: {e}")

        role_by_trip = {m.trip_id: m.role for m in memberships}

        response = []
        for plan in plans:
            role = role_by_trip.get(plan.id)
            if not role:
                raise HTTPException(status_code=404, detail="No RBAC found.")
            response.append({
                "id": plan.id,
                "planning_type": plan.planning_type,
                "routing_style": plan.routing_style,
                "origin": plan.origin,
                "destinations": plan.destinations,
                "start_date": plan.start_date,
                "end_date": plan.end_date,
                "adults": plan.adults,
                "children": plan.children,
                "status": plan.status,
                "role": role,
                "owner": _user_response(plan.owner),
            })
        return {"message": "Plans fetched successfully.", "status_code": 200, "plans": response}


"""
Get trip members and pending invitations for the share panel.
"""
@router.get("/{id}/members", response_model=dict)
async def get_trip_members(token: str, id: str):
    user_id = await _decode_user_id(token)

    async with Session() as db:
        try:
            await _load_user_or_404(db, user_id)
            caller = await _get_accepted_member(db, id, user_id)
            if not caller:
                return {"message": "You are not authorized to view this plan.", "status_code": 403, "members": []}

            trip = (await db.execute(select(Trip).where(Trip.id == id))).scalar_one_or_none()
            if not trip:
                return {"message": "Plan not found.", "status_code": 404, "members": []}

            members = (await db.execute(
                select(TripMember)
                .where(TripMember.trip_id == id)
                .order_by(TripMember.created_at.asc())
            )).scalars().all()

            visible_members = [
                _member_response(member, owner_id=trip.owner_id)
                for member in members
                if member.user_id is not None or member.invited_email
            ]
            return {
                "message": "Trip members fetched successfully.",
                "status_code": 200,
                "current_user_role": _role_value(caller.role),
                "owner": _user_response(trip.owner),
                "members": visible_members,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Failed to fetch trip members", trip_id=id, user_id=user_id, error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to fetch trip members: {e}")


"""
Invite a user to view or edit a generated itinerary.
"""
@router.post("/{id}/share", response_model=dict)
async def share_trip(id: str, token: str, req: ShareTripRequest):
    user_id = await _decode_user_id(token)
    email = _normalize_email(req.email)
    if not _is_valid_email(email):
        raise HTTPException(status_code=400, detail="Invalid email address.")
    if req.role not in {TripRole.SHARED_EDITOR.value, TripRole.SHARED_VIEWER.value}:
        raise HTTPException(status_code=400, detail="Invalid sharing role.")

    async with Session() as db:
        try:
            inviter = await _load_user_or_404(db, user_id)
            caller = await _get_accepted_member(db, id, user_id)
            if not caller or not _can_share(_role_value(caller.role)):
                return {"message": "You are not authorized to share this itinerary.", "status_code": 403}

            trip = (await db.execute(select(Trip).where(Trip.id == id))).scalar_one_or_none()
            if not trip:
                return {"message": "Plan not found.", "status_code": 404}

            itinerary = (await db.execute(
                select(TripItinerary).where(TripItinerary.trip_id == id)
            )).scalar_one_or_none()
            if not itinerary or _role_value(itinerary.status) != "generated":
                return {"message": "Only generated itineraries can be shared.", "status_code": 400}

            if _normalize_email(inviter.email) == email:
                raise HTTPException(status_code=400, detail="You already have access to this itinerary.")

            recipient = (await db.execute(
                select(User).where(sa_func.lower(User.email) == email)
            )).scalar_one_or_none()

            existing = None
            if recipient:
                existing = (await db.execute(
                    select(TripMember).where(
                        TripMember.trip_id == id,
                        TripMember.user_id == recipient.id,
                    )
                )).scalar_one_or_none()
            if not existing:
                existing = (await db.execute(
                    select(TripMember).where(
                        TripMember.trip_id == id,
                        sa_func.lower(TripMember.invited_email) == email,
                    )
                )).scalar_one_or_none()

            if existing and _role_value(existing.role) == TripRole.OWNER.value:
                raise HTTPException(status_code=400, detail="The owner already has access.")

            role = TripRole(req.role)
            if existing and existing.invitation_status == TripInvitationStatus.ACCEPTED.value:
                existing.role = role
                await db.commit()
                return {
                    "message": "Access updated successfully.",
                    "status_code": 200,
                    "member": _member_response(existing, owner_id=trip.owner_id),
                }

            invitation_token, invitation_token_hash = _new_invitation_token()
            expires_at = datetime.now(timezone.utc) + timedelta(days=14)

            if existing:
                existing.role = role
                existing.user_id = recipient.id if recipient else existing.user_id
                existing.invited_by_user_id = user_id
                existing.invited_email = email
                existing.invitation_status = TripInvitationStatus.PENDING.value
                existing.invitation_token_hash = invitation_token_hash
                existing.expires_at = expires_at
            else:
                existing = TripMember(
                    trip_id=id,
                    user_id=recipient.id if recipient else None,
                    invited_by_user_id=user_id,
                    invited_email=email,
                    role=role,
                    invitation_status=TripInvitationStatus.PENDING.value,
                    invitation_token_hash=invitation_token_hash,
                    expires_at=expires_at,
                )
                db.add(existing)

            await db.commit()
            await db.refresh(existing)

            trip_title = itinerary.title or "a BonPlan itinerary"
            accept_link = f"{settings.FRONTEND_URL}/share-invite?token={invitation_token}"
            inviter_name = f"{inviter.first_name} {inviter.last_name}".strip() or inviter.email
            role_label = "Can Edit" if role == TripRole.SHARED_EDITOR else "Can View"
            recipient_name = recipient.first_name if recipient else "there"
            await send_email(
                email,
                f"BonPlan.ai - {inviter.first_name} shared an itinerary with you",
                _format_invitation_email(
                    recipient_name=recipient_name,
                    inviter_name=inviter_name,
                    trip_title=trip_title,
                    role_label=role_label,
                    accept_link=accept_link,
                ),
                inline_images={BONPLAN_LOGO_CID: BONPLAN_LOGO_PATH},
            )

            return {
                "message": "Invitation sent successfully.",
                "status_code": 200,
                "member": _member_response(existing, owner_id=trip.owner_id),
            }
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            logger.exception("Failed to share trip", trip_id=id, user_id=user_id, email=email, error=str(e))
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to share itinerary: {e}")


"""
Create a one-use invitation link for a generated itinerary.
"""
@router.post("/{id}/share-link", response_model=dict)
async def create_trip_share_link(id: str, token: str, req: CreateShareLinkRequest):
    user_id = await _decode_user_id(token)
    if req.role not in {TripRole.SHARED_EDITOR.value, TripRole.SHARED_VIEWER.value}:
        raise HTTPException(status_code=400, detail="Invalid sharing role.")

    async with Session() as db:
        try:
            await _load_user_or_404(db, user_id)
            caller = await _get_accepted_member(db, id, user_id)
            if not caller or not _can_share(_role_value(caller.role)):
                return {"message": "You are not authorized to share this itinerary.", "status_code": 403}

            trip = (await db.execute(select(Trip).where(Trip.id == id))).scalar_one_or_none()
            if not trip:
                return {"message": "Plan not found.", "status_code": 404}

            itinerary = (await db.execute(
                select(TripItinerary).where(TripItinerary.trip_id == id)
            )).scalar_one_or_none()
            if not itinerary or _role_value(itinerary.status) != "generated":
                return {"message": "Only generated itineraries can be shared.", "status_code": 400}

            invitation_token, invitation_token_hash = _new_invitation_token()
            link_member = TripMember(
                trip_id=id,
                invited_by_user_id=user_id,
                role=TripRole(req.role),
                invitation_status=TripInvitationStatus.PENDING.value,
                invitation_token_hash=invitation_token_hash,
                expires_at=datetime.now(timezone.utc) + timedelta(days=14),
            )
            db.add(link_member)
            await db.commit()

            return {
                "message": "Share link created successfully.",
                "status_code": 200,
                "url": f"{settings.FRONTEND_URL}/share-invite?token={invitation_token}",
                "role": req.role,
            }
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            logger.exception("Failed to create share link", trip_id=id, user_id=user_id, error=str(e))
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to create share link: {e}")


"""
Accept a pending trip invitation.
"""
@router.post("/invitations/accept", response_model=dict)
async def accept_trip_invitation(auth_token: str, invitation_token: str):
    user_id = await _decode_user_id(auth_token)
    token_hash = _hash_invitation_token(invitation_token)

    async with Session() as db:
        try:
            user = await _load_user_or_404(db, user_id)
            invitation = (await db.execute(
                select(TripMember).where(TripMember.invitation_token_hash == token_hash)
            )).scalar_one_or_none()
            if not invitation:
                raise HTTPException(status_code=404, detail="Invitation not found.")

            if invitation.invitation_status == TripInvitationStatus.ACCEPTED.value:
                if str(invitation.user_id) == str(user_id):
                    trip = (await db.execute(select(Trip).where(Trip.id == invitation.trip_id))).scalar_one_or_none()
                    return {
                        "message": "Invitation already accepted.",
                        "status_code": 200,
                        "trip_id": invitation.trip_id,
                        "planning_type": trip.planning_type if trip else PlanningType.SOLO.value,
                        "role": _role_value(invitation.role),
                    }
                raise HTTPException(status_code=400, detail="This invitation has already been used.")

            if invitation.expires_at and invitation.expires_at < datetime.now(timezone.utc):
                raise HTTPException(status_code=400, detail="Invitation has expired.")

            if invitation.invited_email and _normalize_email(user.email) != _normalize_email(invitation.invited_email):
                raise HTTPException(status_code=403, detail="This invitation was sent to a different email address.")

            existing = (await db.execute(
                select(TripMember).where(
                    TripMember.trip_id == invitation.trip_id,
                    TripMember.user_id == user_id,
                    TripMember.id != invitation.id,
                )
            )).scalar_one_or_none()
            if existing:
                if _role_value(existing.role) != TripRole.OWNER.value:
                    existing.role = invitation.role
                    existing.invitation_status = TripInvitationStatus.ACCEPTED.value
                    existing.accepted_at = datetime.now(timezone.utc)
                    existing.invited_email = existing.invited_email or invitation.invited_email
                await db.delete(invitation)
                await db.commit()
                trip = (await db.execute(select(Trip).where(Trip.id == existing.trip_id))).scalar_one_or_none()
                return {
                    "message": "You already have access to this itinerary.",
                    "status_code": 200,
                    "trip_id": existing.trip_id,
                    "planning_type": trip.planning_type if trip else PlanningType.SOLO.value,
                    "role": _role_value(existing.role),
                }

            if invitation.user_id and str(invitation.user_id) != str(user_id):
                raise HTTPException(status_code=403, detail="This invitation belongs to a different account.")

            invitation.user_id = user_id
            invitation.invitation_status = TripInvitationStatus.ACCEPTED.value
            invitation.accepted_at = datetime.now(timezone.utc)

            await db.commit()

            trip = (await db.execute(select(Trip).where(Trip.id == invitation.trip_id))).scalar_one_or_none()
            return {
                "message": "Invitation accepted successfully.",
                "status_code": 200,
                "trip_id": invitation.trip_id,
                "planning_type": trip.planning_type if trip else PlanningType.SOLO.value,
                "role": _role_value(invitation.role),
            }
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            logger.exception("Failed to accept invitation", user_id=user_id, error=str(e))
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to accept invitation: {e}")


"""
Elevate a viewer to editor from an owner email action.
"""
@router.post("/invitations/elevate", response_model=dict)
async def elevate_trip_access(auth_token: str, invitation_token: str):
    user_id = await _decode_user_id(auth_token)
    token_hash = _hash_invitation_token(invitation_token)

    async with Session() as db:
        try:
            owner = await _load_user_or_404(db, user_id)
            member = (await db.execute(
                select(TripMember).where(TripMember.invitation_token_hash == token_hash)
            )).scalar_one_or_none()
            if not member:
                raise HTTPException(status_code=404, detail="Access request not found.")
            if member.expires_at and member.expires_at < datetime.now(timezone.utc):
                raise HTTPException(status_code=400, detail="Access request has expired.")

            trip = (await db.execute(select(Trip).where(Trip.id == member.trip_id))).scalar_one_or_none()
            if not trip:
                raise HTTPException(status_code=404, detail="Plan not found.")
            if trip.owner_id != owner.id:
                raise HTTPException(status_code=403, detail="Only the owner can elevate access.")
            if member.invitation_status != TripInvitationStatus.ACCEPTED.value:
                raise HTTPException(status_code=400, detail="The requester has not accepted the itinerary invitation.")
            if _role_value(member.role) == TripRole.OWNER.value:
                raise HTTPException(status_code=400, detail="Owner access cannot be changed.")

            member.role = TripRole.SHARED_EDITOR
            member.invitation_token_hash = None
            member.expires_at = None
            await db.commit()

            return {
                "message": "Access elevated successfully.",
                "status_code": 200,
                "trip_id": trip.id,
                "planning_type": trip.planning_type,
                "role": _role_value(member.role),
            }
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            logger.exception("Failed to elevate access", user_id=user_id, error=str(e))
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to elevate access: {e}")


"""
Request editor access for a shared viewer.
"""
@router.post("/{id}/access-requests/edit", response_model=dict)
async def request_edit_access(id: str, token: str):
    user_id = await _decode_user_id(token)

    async with Session() as db:
        try:
            requester = await _load_user_or_404(db, user_id)
            member = await _get_accepted_member(db, id, user_id)
            if not member:
                return {"message": "You are not authorized to request access for this itinerary.", "status_code": 403}
            if _role_value(member.role) == TripRole.SHARED_EDITOR.value:
                return {"message": "You already have editing access.", "status_code": 200}
            if _role_value(member.role) != TripRole.SHARED_VIEWER.value:
                return {"message": "Only viewers can request editing access.", "status_code": 400}

            trip = (await db.execute(select(Trip).where(Trip.id == id))).scalar_one_or_none()
            if not trip:
                return {"message": "Plan not found.", "status_code": 404}

            itinerary = (await db.execute(
                select(TripItinerary).where(TripItinerary.trip_id == id)
            )).scalar_one_or_none()
            if not itinerary or _role_value(itinerary.status) != "generated":
                return {"message": "Only generated itineraries can request editing access.", "status_code": 400}

            owner = trip.owner
            if not owner:
                raise HTTPException(status_code=404, detail="Trip owner not found.")

            elevation_token, elevation_token_hash = _new_invitation_token()
            member.invitation_token_hash = elevation_token_hash
            member.expires_at = datetime.now(timezone.utc) + timedelta(days=14)
            await db.commit()

            trip_title = itinerary.title or "a BonPlan itinerary"
            requester_name = f"{requester.first_name} {requester.last_name}".strip() or requester.email
            owner_name = owner.first_name or "there"
            elevate_link = f"{settings.FRONTEND_URL}/share-invite?action=elevate&token={elevation_token}"
            await send_email(
                owner.email,
                f"BonPlan.ai - {requester.first_name} requested editing access",
                _format_edit_access_request_email(
                    owner_name=owner_name,
                    requester_name=requester_name,
                    requester_email=requester.email,
                    trip_title=trip_title,
                    elevate_link=elevate_link,
                ),
                inline_images={BONPLAN_LOGO_CID: BONPLAN_LOGO_PATH},
            )

            return {"message": "Editing access request sent to the owner.", "status_code": 200}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            logger.exception("Failed to request edit access", trip_id=id, user_id=user_id, error=str(e))
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to request editing access: {e}")


"""
Remove shared access or a pending invitation. Owners only.
"""
@router.delete("/{id}/members/{member_id}", response_model=dict)
async def remove_trip_member(id: str, member_id: str, token: str):
    user_id = await _decode_user_id(token)

    async with Session() as db:
        try:
            await _load_user_or_404(db, user_id)
            caller = await _get_accepted_member(db, id, user_id)
            if not caller or _role_value(caller.role) != TripRole.OWNER.value:
                return {"message": "Only the owner can remove shared access.", "status_code": 403}

            target = (await db.execute(
                select(TripMember).where(
                    TripMember.id == member_id,
                    TripMember.trip_id == id,
                )
            )).scalar_one_or_none()
            if not target:
                return {"message": "Access entry not found.", "status_code": 404}
            if _role_value(target.role) == TripRole.OWNER.value:
                raise HTTPException(status_code=400, detail="Owner access cannot be removed.")

            await db.delete(target)
            await db.commit()
            return {"message": "Access removed successfully.", "status_code": 200}
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            logger.exception("Failed to remove trip member", trip_id=id, member_id=member_id, user_id=user_id, error=str(e))
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to remove access: {e}")

"""
Download the current generated itinerary as a professionally formatted PDF.
"""
@router.get("/{id}/download")
async def download_itinerary_pdf(id: str, token: str):
    user_id = await _decode_user_id(token)

    try:
        from app.services.itinerary_pdf import build_itinerary_pdf, itinerary_pdf_filename
    except ImportError:
        logger.exception("PDF renderer dependencies are not installed")
        raise HTTPException(
            status_code=500,
            detail="PDF renderer dependencies are not installed. Run pip install -r requirements.txt.",
        )

    async with Session() as db:
        try:
            user = await _load_user_or_404(db, user_id)
            caller = await _get_accepted_member(db, id, user_id)
            if not caller:
                raise HTTPException(status_code=403, detail="You are not authorized to download this itinerary.")

            plan = (await db.execute(select(Trip).where(Trip.id == id))).scalar_one_or_none()
            if not plan:
                raise HTTPException(status_code=404, detail="Plan not found.")

            itinerary = (await db.execute(
                select(TripItinerary).where(TripItinerary.trip_id == id)
            )).scalar_one_or_none()
            if not itinerary:
                raise HTTPException(status_code=404, detail="Trip itinerary not found.")
            if _role_value(itinerary.status) != "generated":
                raise HTTPException(status_code=400, detail="Only generated itineraries can be downloaded.")

            pdf_bytes = build_itinerary_pdf(plan, itinerary, generated_for=user)
            filename = itinerary_pdf_filename(itinerary.title, id)
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Cache-Control": "no-store",
                },
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Failed to generate itinerary PDF", trip_id=id, user_id=user_id, error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to generate itinerary PDF: {e}")

"""
Get a plan by id endpoint
"""
@router.get("/{id}", response_model=dict)
async def get_plan(token: str, id: str):
    if not token:
        raise HTTPException(status_code=400, detail="Token is required.")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session. Please log in again.")
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid token.")

    async with Session() as db:
        try:
            user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=404, detail="User not found.")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get plans: {e}")

        try:
            rbac = (await db.execute(
                select(TripMember).where(
                    TripMember.trip_id == id,
                    TripMember.user_id == user_id,
                    TripMember.invitation_status == TripInvitationStatus.ACCEPTED.value,
                )
            )).scalar_one_or_none()
            if not rbac:
                return {"message": "You are not authorized to view this plan.", "status_code": 403, "plan": None}
            role = rbac.role
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get RBAC for plan: {e}")

        try:
            plan = (await db.execute(select(Trip).where(Trip.id == id))).scalar_one_or_none()
            if not plan:
                return {"message": "Plan not found.", "status_code": 404, "plan": None}
        except Exception as e:
            logger.error("Failed to get plan", trip_id=id, user_id=user_id, error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to get plan: {e}")

        planResponse = {
            "id": plan.id,
            "planning_type": plan.planning_type,
            "routing_style": plan.routing_style,
            "origin": plan.origin,
            "destinations": plan.destinations,
            "start_date": plan.start_date,
            "end_date": plan.end_date,
            "pace": plan.pace,
            "budget": plan.budget,
            "adults": plan.adults,
            "children": plan.children,
            "status": plan.status,
            "role": role,
            "owner": _user_response(plan.owner),
            "created_at": plan.created_at,
            "updated_at": plan.updated_at,
        }
        try:
            tripItinerary = (await db.execute(
                select(TripItinerary).where(TripItinerary.trip_id == id)
            )).scalar_one_or_none()
            if not tripItinerary:
                return {"message": "Trip itinerary not found.", "status_code": 404, "plan": planResponse, "tripItinerary": None}
        except Exception:
            return {"message": "Trip itinerary not found.", "status_code": 404, "plan": planResponse, "tripItinerary": None}

        tripItineraryResponse = {
            "id": tripItinerary.id,
            "title": tripItinerary.title,
            "origin": tripItinerary.origin,
            "destinations": tripItinerary.destinations,
            "start_date": tripItinerary.start_date,
            "end_date": tripItinerary.end_date,
            "cost": tripItinerary.cost,
            "days": tripItinerary.days,
            "events": tripItinerary.events,
            "tips": tripItinerary.tips,
            "status": tripItinerary.status,
            "created_at": tripItinerary.created_at,
            "updated_at": tripItinerary.updated_at,
        }
        return {"message": "Plan fetched successfully.", "status_code": 200, "plan": planResponse, "tripItinerary": tripItineraryResponse}

"""
Delete a plan by id endpoint
"""
@router.delete("/{id}", response_model=dict)
async def delete_plan(token: str, id: str):
    if not token:
        raise HTTPException(status_code=400, detail="Token is required.")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session. Please log in again.")
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid token.")

    async with Session() as db:
        try:
            user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            if not user:
                raise HTTPException(status_code=404, detail="User not found.")
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to fetch user for deletion", trip_id=id, user_id=user_id, error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to delete plan: {e}")

        try:
            rbac = (await db.execute(
                select(TripMember).where(
                    TripMember.trip_id == id,
                    TripMember.user_id == user_id,
                    TripMember.invitation_status == TripInvitationStatus.ACCEPTED.value,
                )
            )).scalar_one_or_none()
            if not rbac:
                return {"message": "You are not authorized to delete this plan.", "status_code": 403}
            role = _role_value(rbac.role)
            if role != TripRole.OWNER.value:
                return {"message": "You are not authorized to delete this plan.", "status_code": 403}
        except Exception as e:
            logger.error("Failed to get RBAC for deletion", trip_id=id, user_id=user_id, error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to get RBAC for plan: {e}")

        try:
            plan = (await db.execute(select(Trip).where(Trip.id == id))).scalar_one_or_none()
            if not plan:
                return {"message": "Plan not found.", "status_code": 404}
        except Exception as e:
            logger.error("Failed to fetch plan for deletion", trip_id=id, user_id=user_id, error=str(e))
            raise HTTPException(status_code=500, detail=f"Failed to delete plan: {e}")

        try:
            await db.delete(plan)
            await db.commit()
            return {"message": "Plan deleted successfully.", "status_code": 200}
        except Exception as e:
            logger.error("Failed to delete plan", trip_id=id, user_id=user_id, error=str(e))
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to delete plan: {e}")
