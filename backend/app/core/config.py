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
    AGENT_URL: str = os.getenv("AGENT_URL", "http://localhost:8001")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # Project settings
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "BonPlan.ai")
    AGENT_NAME: str = os.getenv("AGENT_NAME", "BonPlan.ai - Agent")
    PROJECT_VERSION: str = os.getenv("PROJECT_VERSION", "v0.0.0")
    AGENT_VERSION: str = os.getenv("AGENT_VERSION", "v0.0.0")

    # PostgreSQL settings
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "bonplan_admin")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "secure_password")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "bonplan_db")

    # Google Cloud Platform settings
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY")

    # Gemini API Keys
    SERPER_CONTENT_PARSER_API_KEY: str = os.getenv("SERPER_CONTENT_PARSER_API_KEY")
    PLANNER_AGENT_API_KEY: str = os.getenv("PLANNER_AGENT_API_KEY")

    # Gemini Models
    SERPER_CONTENT_PARSER_MODEL: str = "gemma-4-26b-a4b-it"
    PLANNER_AGENT_MODEL: str = "gemma-4-31b-it"#"gemma-4-31b-it" #"gemini-3.1-flash-lite-preview" #"gemma-4-26b-a4b-it" #"gemini-2.5-flash-lite"
    PLANNER_AGENT_MODEL_CONTEXT_WINDOW: int = 256000 # 256K

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
    FALLBACK_IMAGE: str = os.getenv("FALLBACK_IMAGE", "https://images.unsplash.com/photo-1488085061387-422e29b40080?q=80&w=3131&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D")


    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

settings = Settings()