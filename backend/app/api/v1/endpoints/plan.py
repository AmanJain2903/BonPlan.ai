# backend/app/api/v1/endpoints/plan.py

"""
This file contains the plan endpoints for the v1 version of the API.
"""

from app.database.database import Session, get_db
from app.database.models.tripsTable import Trip, PlanningType, RoutingStyle, PlanStatus
from app.database.models.usersTable import User
from app.database.models.tripMembersTable import TripMember, TripRole
from app.data.labels import paceLabels, budgetLabels
from app.core.config import settings

import jwt
import json

from fastapi import HTTPException, Request, APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.agent.planner import generate_trip_itinerary

from datetime import datetime
from zoneinfo import ZoneInfo

import logging
logger = logging.getLogger(__name__)

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
def draft_plan( token: str, data: dict, db: Session = Depends(get_db)):
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
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
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
        db.commit()
        db.refresh(newTrip)

        newTripMember = TripMember(
            trip_id=newTrip.id,
            user_id=user_id,
            role=TripRole.OWNER,
            trip_preferences=preferences,
        )
        db.add(newTripMember)
        db.commit()
        db.refresh(newTripMember)
        return {"message": "Plan drafted successfully.", "status_code": 201, "trip_id": newTrip.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to draft plan: {e}")

"""
Get RBAC of a user for a plan by id endpoint
"""
@router.get("/rbac/{id}", response_model=dict)
def get_rbac_for_plan( token: str, id: str, db: Session = Depends(get_db)):
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
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get RBAC for trip: {e}")
    try:
        trip = db.query(Trip).filter(Trip.id == id).first()
        if not trip:
            return {"message": "Trip not found.", "status_code": 404, "rbac": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get RBAC for trip: {e}")
    try:
        rbac = db.query(TripMember).filter(TripMember.trip_id == id, TripMember.user_id == user_id).first()
        if not rbac:
            return {"message": "You lack this access.", "status_code": 403, "rbac": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get RBAC for draft plan: {e}")
    return {"message": "RBAC fetched successfully.", "status_code": 200, "rbac": rbac.role}

"""
Get all plans for a user with RBAC endpoint
"""
@router.get("/plans", response_model=dict)
def get_plans( token: str, db: Session = Depends(get_db)):
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
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get plans: {e}")
    try:
        memberships = db.query(TripMember).filter(TripMember.user_id == user_id).all()
        if not memberships:
            return {"message": "You have no plans yet.", "status_code": 404, "plans": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get memberships: {e}")
    try:
        planIds = []
        for membership in memberships:
            plan = db.query(Trip).filter(Trip.id == membership.trip_id).first()
            if plan:
                planIds.append(plan.id)
        plans = db.query(Trip).filter(Trip.id.in_(planIds)).order_by(Trip.updated_at.desc()).all()
        if not plans:
            return {"message": "You have no plans yet.", "status_code": 404, "plans": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get plans: {e}")
    
    response = []
    for plan in plans:
        rbac = db.query(TripMember).filter(TripMember.trip_id == plan.id, TripMember.user_id == user_id).first()
        if not rbac:
            raise HTTPException(status_code=404, detail="No RBAC found.")
        role = rbac.role
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
def get_plan( token: str, id: str, db: Session = Depends(get_db)):
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
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get plans: {e}")
    try:
        rbac = db.query(TripMember).filter(TripMember.trip_id == id, TripMember.user_id == user_id).first()
        if not rbac:
            return {"message": "You are not authorized to view this plan.", "status_code": 403, "plan": None}
        role = rbac.role
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get RBAC for plan: {e}")
    try:
        plan = db.query(Trip).filter(Trip.id == id).first()
        if not plan:
            return {"message": "Plan not found.", "status_code": 404, "plan": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get plan: {e}")
    
    response = {
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
    return {"message": "Plan fetched successfully.", "status_code": 200, "plan": response}

"""
Update a plan by id endpoint
"""
@router.put("/{id}", response_model=dict)
def update_plan( token: str, id: str, data: dict, db: Session = Depends(get_db)):
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
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update plan: {e}")
    try:
        rbac = db.query(TripMember).filter(TripMember.trip_id == id, TripMember.user_id == user_id).first()
        if not rbac:
            return {"message": "You are not authorized to update this plan.", "status_code": 403, "plan": None}
        role = rbac.role
        if role == "shared_viewer":
            return {"message": "You are not authorized to update this plan.", "status_code": 403, "plan": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get RBAC for plan: {e}")
    try:
        plan = db.query(Trip).filter(Trip.id == id).first()
        if not plan:
            return {"message": "Plan not found.", "status_code": 404, "plan": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update plan: {e}")
    try:
        startDate = data.get("startDate")
        startDate_utc_time_string, startDate_utc_timestamp = get_utc_datetime(startDate)
        startDate_local_time_string = get_local_time_string(startDate)
        startDate["utcTimeString"] = startDate_utc_time_string
        startDate["utcTimestamp"] = startDate_utc_timestamp
        startDate["localTimeString"] = startDate_local_time_string
        endDate = data.get("endDate")
        endDate_utc_time_string, endDate_utc_timestamp = get_utc_datetime(endDate)
        endDate_local_time_string = get_local_time_string(endDate, isEndTime=True)
        endDate["utcTimeString"] = endDate_utc_time_string
        endDate["utcTimestamp"] = endDate_utc_timestamp
        endDate["localTimeString"] = endDate_local_time_string
        plan.start_date = startDate
        plan.end_date = endDate
        plan.pace = data.get("pace")
        plan.budget = data.get("budget")
        plan.adults = data.get("adults")
        plan.children = data.get("children")
        plan.status = data.get("status")
        db.commit()
        db.refresh(plan)
        return {"message": "Plan updated successfully.", "status_code": 200, "plan": plan}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update plan: {e}")

"""
Delete a plan by id endpoint
"""
@router.delete("/{id}", response_model=dict)
def delete_plan( token: str, id: str, db: Session = Depends(get_db)):
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
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete plan: {e}")
    try:
        rbac = db.query(TripMember).filter(TripMember.trip_id == id, TripMember.user_id == user_id).first()
        if not rbac:
            return {"message": "You are not authorized to delete this plan.", "status_code": 403}
        role = rbac.role
        if role != "owner":
            return {"message": "You are not authorized to delete this plan.", "status_code": 403}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get RBAC for plan: {e}")
    try:
        plan = db.query(Trip).filter(Trip.id == id).first()
        if not plan:
            return {"message": "Plan not found.", "status_code": 404}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete plan: {e}")
    try:
        db.delete(plan)
        db.commit()
        return {"message": "Plan deleted successfully.", "status_code": 200}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete plan: {e}")

"""
Generate Solo Plan via SSE endpoint
"""
@router.post("/generate/solo/{id}")
async def generate_solo_plan(request: Request, id: str, db: Session = Depends(get_db)):
    # 1. Validate Token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header.")
    token = auth_header.split(" ")[1]
    
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("user_id")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid session. Please log in again.")
        
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid token.")
        
    # 2. Extract Body Parameters (chatInput, mode)
    try:
        body = await request.json()
        chat_input = body.get("chatInput", "")
        mode = body.get("mode", "autonomous")
    except Exception:
        chat_input = ""
        mode = "autonomous"


    # 3. Authenticate and Gather Plan Data
    try:
        rbac = db.query(TripMember).filter(TripMember.trip_id == id, TripMember.user_id == user_id).first()
        if not rbac or rbac.role not in ["owner", "shared_editor"]:
            raise HTTPException(status_code=403, detail="Not authorized to generate or edit this plan.")
        
        plan = db.query(Trip).filter(Trip.id == id).first()
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found.")
        
        plan.status = PlanStatus.GENERATING
        db.commit()
        db.refresh(plan)
            
        # Parse Destinations correctly depending on if it's a stringified JSON array or multiple records
        destinations_list = plan.destinations
        if isinstance(destinations_list, str):
            try:
                destinations_list = json.loads(destinations_list)
            except:
                destinations_list = []
                
        if isinstance(plan.start_date, str):
            start_date = json.loads(plan.start_date)
        else:
            start_date = plan.start_date
            
        if isinstance(plan.end_date, str):
            end_date = json.loads(plan.end_date)
        else:
            end_date = plan.end_date
            
        trip_payload = {
            "hasMultipleDestinations": len(destinations_list) > 1,
            "planning_type": plan.planning_type.value if hasattr(plan.planning_type, 'value') else plan.planning_type,
            "routing_style": plan.routing_style.value if hasattr(plan.routing_style, 'value') else plan.routing_style,
            "origin": json.loads(plan.origin) if isinstance(plan.origin, str) else plan.origin,
            "destinations": destinations_list,
            "start_date": start_date,
            "end_date": end_date,
            "pace": plan.pace,
            "budget": plan.budget,
            "adults": plan.adults,
            "children": plan.children,
            "preferences": rbac.trip_preferences or {},
            "textualContext": chat_input
        }
    except Exception as e:
        plan.status = PlanStatus.DRAFT
        db.commit()
        db.refresh(plan)
        raise HTTPException(status_code=500, detail=f"Failed to assemble Trip data: {e}")

    # 4. Stream Generator Wrapper
    async def event_generator():
        try:
            async for chunk in generate_trip_itinerary(
                trip_payload, 
                mode=mode, 
                owner_id=str(user_id), 
                trip_id=str(plan.id),
                cancellation_callback=request.is_disconnected
            ):
                yield f"data: {json.dumps(chunk)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
    # 5. Return SSE Response
    return StreamingResponse(event_generator(), media_type="text/event-stream")