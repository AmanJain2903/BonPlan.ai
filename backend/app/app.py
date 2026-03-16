# backend/app/app.py

"""
This file contains the main application for the backend application.
"""

from fastapi.middleware.cors import CORSMiddleware
from app.api.router import router
from fastapi import FastAPI

from app.database.database import Base, engine
from app.core.config import settings
from app.database import models

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
)

@app.on_event("startup")
def on_startup():
    # Base.metadata.drop_all(bind=engine) # <--- DELETE DATA
    Base.metadata.create_all(bind=engine)

# Allow React (Port 5173) to talk to Python
origins = [
    settings.FRONTEND_URL,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)
# ----------------------

# Include all our routes
app.include_router(router, prefix="/api/v1")