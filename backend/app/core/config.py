# backend/app/core/config.py

"""
Configuration settings for the backend application.
"""

from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from pathlib import Path
import platform
import os

# Load environment variables
load_dotenv()

class Settings(BaseSettings):

    # Deployment settings
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # Project settings
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "BonPlan.ai")
    PROJECT_VERSION: str = os.getenv("PROJECT_VERSION", "v0.0.0")

    # PostgreSQL settings
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "bonplan_admin")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "secure_password")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "bonplan_db")

    # Google Cloud Platform settings
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_MAPS_API_KEY_UNRESTRICTED: str = os.getenv("GOOGLE_MAPS_API_KEY_UNRESTRICTED")

    # Gemini API Keys
    SERPER_CONTENT_PARSER_API_KEY: str = os.getenv("SERPER_CONTENT_PARSER_API_KEY")

    # Gemini Models
    SERPER_CONTENT_PARSER_MODEL: str = "gemini-2.5-flash-lite"

    # Serper API key
    SERPER_API_KEY: str = os.getenv("SERPER_API_KEY")

    # Rapid API key
    RAPID_API_KEY: str = os.getenv("RAPID_API_KEY")

    # Secret key for JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY")

    # Email settings
    SENDER_EMAIL: str = os.getenv("SENDER_EMAIL")
    GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD")

    # Fallbacks
    FALLBACK_IMAGE: str = os.getenv("FALLBACK_IMAGE", "https://unsplash.com/photos/airplanes-window-view-of-sky-during-golden-hour-oCdVtGFeDC0")


    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

settings = Settings()