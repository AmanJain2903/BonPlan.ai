# backend/app/api/v1/endpoints/plan.py

"""
This file contains the plan endpoints for the v1 version of the API.
"""

from app.database.database import Session, get_db
from app.database.models.tripsTable import Trip, PlanningType, RoutingStyle
from app.database.models.usersTable import User
from app.database.models.tripMembersTable import TripMember, TripRole
from app.data.labels import paceLabels, budgetLabels
from app.core.config import settings

import jwt

from fastapi import HTTPException, Request, APIRouter, Depends


router = APIRouter()

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
        endDate = tripData.get("endDate")
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
            is_draft=True,
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
            "is_draft": plan.is_draft,
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
        "is_draft": plan.is_draft,
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
        plan.start_date = data.get("startDate")
        plan.end_date = data.get("endDate")
        plan.pace = data.get("pace")
        plan.budget = data.get("budget")
        plan.adults = data.get("adults")
        plan.children = data.get("children")
        plan.is_draft = data.get("isDraft")
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