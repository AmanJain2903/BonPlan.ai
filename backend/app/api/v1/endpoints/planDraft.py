# backend/app/api/v1/endpoints/plan.py

"""
This file contains the plan endpoints for the v1 version of the API.
"""

from app.database.database import Session, get_db
from app.database.models.tripsTable import Trip  
from app.database.models.usersTable import User
from app.database.models.tripMembersTable import TripMember
from app.data.labels import paceLabels, budgetLabels
from app.core.config import settings

import jwt

from fastapi import HTTPException, Request, APIRouter, Depends


router = APIRouter()

"""
Draft a plan endpoint
"""
@router.post("/draft-plan", response_model=dict)
def draftPlan( token: str, data: dict, db: Session = Depends(get_db)):
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
        endDate = tripData.get("endDate")
        pace = tripData.get("pace")
        budget = tripData.get("budget")
        conversationalContext = tripData.get("conversationalContext")
        adults = tripData.get("adults")
        children = tripData.get("children")
        tripStatus = "draft"
        if origin is None or destinations is None or startDate is None or endDate is None or pace is None or budget is None or conversationalContext is None or adults is None or children is None:
            raise HTTPException(status_code=400, detail="All fields are required.")
        
        newTrip = Trip(
            owner_id=user_id,
            planning_type=planningType,
            routing_style=routingStyle,
            origin=origin,
            destinations=destinations,
            start_date=startDate,
            end_date=endDate,
            pace=paceLabels[pace],
            budget=budgetLabels[budget],
            conversational_context=conversationalContext,
            adults=adults,
            children=children,
            trip_status=tripStatus,
        )
        db.add(newTrip)
        db.commit()
        db.refresh(newTrip)

        newTripMember = TripMember(
            trip_id=newTrip.id,
            user_id=user_id,
            role="owner",
        )
        db.add(newTripMember)
        db.commit()
        db.refresh(newTripMember)
        return {"message": "Plan drafted successfully.", "status_code": 201, "trip_id": newTrip.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to draft plan: {e}")

"""
Get all draft plans for a user endpoint
"""
@router.get("/draft-plans", response_model=dict)
def getDraftPlans( token: str, db: Session = Depends(get_db)):
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
        raise HTTPException(status_code=500, detail=f"Failed to get draft plans: {e}")
    try:
        draftPlans = db.query(Trip).filter(Trip.owner_id == user_id, Trip.trip_status == "draft").order_by(Trip.updated_at.desc()).all()
        if not draftPlans:
            raise HTTPException(status_code=404, detail="No draft plans found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get draft plans: {e}")
    
    response = []
    for draftPlan in draftPlans:
        response.append({
            "id": draftPlan.id,
            "planning_type": draftPlan.planning_type,
            "routing_style": draftPlan.routing_style,
            "origin": draftPlan.origin,
            "destinations": draftPlan.destinations,
            "start_date": draftPlan.start_date,
            "end_date": draftPlan.end_date,
            "adults": draftPlan.adults,
            "children": draftPlan.children
        })
    return {"message": "Draft plans fetched successfully.", "status_code": 200, "draft_plans": response}