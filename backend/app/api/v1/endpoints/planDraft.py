# backend/app/api/v1/endpoints/plan.py

"""
This file contains the plan endpoints for the v1 version of the API.
"""

from app.database.database import Session, get_db
from app.database.models.tripsTable import Trip  
from app.database.models.usersTable import User
from app.database.models.tripMembersTable import TripMember
from app.core.config import settings

import jwt

from fastapi import HTTPException, Request, APIRouter, Depends


router = APIRouter()


"""
Create trip endpoint
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
        tripStatus = "Draft"
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
            pace=pace,
            budget=budget,
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