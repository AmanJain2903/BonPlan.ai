# backend/app/api/v1/endpoints/plan.py

"""
This file contains the plan endpoints for the v1 version of the API.
"""

import jwt

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException, APIRouter
from sqlalchemy import select

from app.core.config import settings
from app.data.labels import paceLabels, budgetLabels
from app.database.database import Session
from app.database.models.tripsTable import Trip, PlanningType, RoutingStyle, PlanStatus
from app.database.models.tripItinerariesTable import TripItinerary
from app.database.models.usersTable import User
from app.database.models.tripMembersTable import TripMember, TripRole

router = APIRouter()

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
            import traceback
            error_message = traceback.format_exc()
            print(error_message)
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
                select(TripMember).where(TripMember.trip_id == id, TripMember.user_id == user_id)
            )).scalar_one_or_none()
            if not rbac:
                return {"message": "You lack this access.", "status_code": 403, "rbac": None}
        except Exception as e:
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
                select(TripMember).where(TripMember.user_id == user_id)
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
            })
        return {"message": "Plans fetched successfully.", "status_code": 200, "plans": response}

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
                select(TripMember).where(TripMember.trip_id == id, TripMember.user_id == user_id)
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
            raise HTTPException(status_code=500, detail=f"Failed to delete plan: {e}")

        try:
            rbac = (await db.execute(
                select(TripMember).where(TripMember.trip_id == id, TripMember.user_id == user_id)
            )).scalar_one_or_none()
            if not rbac:
                return {"message": "You are not authorized to delete this plan.", "status_code": 403}
            role = rbac.role
            if role != "owner":
                return {"message": "You are not authorized to delete this plan.", "status_code": 403}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get RBAC for plan: {e}")

        try:
            plan = (await db.execute(select(Trip).where(Trip.id == id))).scalar_one_or_none()
            if not plan:
                return {"message": "Plan not found.", "status_code": 404}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete plan: {e}")

        try:
            await db.delete(plan)
            await db.commit()
            return {"message": "Plan deleted successfully.", "status_code": 200}
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to delete plan: {e}")
