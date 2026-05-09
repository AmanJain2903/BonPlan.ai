# backend/app/core/config.py

"""
Configuration settings for the backend application.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from pathlib import Path
import platform
import os

# Load environment variables
load_dotenv()

class Settings(BaseSettings):

    LOCAL_DEVELOPMENT: bool = False

    # Deployment settings
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    AGENT_URL: str = os.getenv("AGENT_URL", "http://localhost:8001")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # Services settings
    KEEPALIVE_INTERVAL_SECONDS: int = 600 # 10 minutes

    # Logging settings
    LOG_ROOT: str = "backend/logs"

    # Project settings
    PROJECT_NAME: str = "BonPlan.ai"
    AGENT_NAME: str = "BonPlan.ai - Agent"
    PROJECT_VERSION: str = os.getenv("PROJECT_VERSION", "v1.0.0") # Version is not set in environment for production build. Set fallback for the production build. Local and Staging uses the Environment Variable.
    AGENT_VERSION: str = os.getenv("AGENT_VERSION", "v1.0.0") # Version is not set in environment for production build. Set fallback for the production build. Local and Staging uses the Environment Variable.

    # PostgreSQL settings
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "bonplan_admin")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "secure_password")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "bonplan_db")

    POSTGRES_URL: str = os.getenv("POSTGRES_URL", "postgresql+asyncpg://bonplan_admin:secure_password@localhost:5432/bonplan_db")

    @property
    def DATABASE_URL(self) -> str:
        if self.LOCAL_DEVELOPMENT:
            return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        else:
            if "asyncpg" not in self.POSTGRES_URL:
                return "postgresql+asyncpg://" + self.POSTGRES_URL.split("://")[1]
            return self.POSTGRES_URL

    # Redis settings
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Redis Rate Limiter settings
    REDIS_RATE_LIMIT_PREFIX: str = "rl"
    RATE_LIMITER_MODE: str = "strict" # "lenient" (default) — allow the call, log the failure. "strict" — treat as rate-limited (raise). In staging and production, set to "strict".
    RATE_LIMITER_CONFIG_TTL_SECONDS: int = "60"
    RATE_LIMITER_RESET_TZ: str = "America/Los_Angeles"

    # Google Cloud Platform settings
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY")

    # LiteLLM provider API keys. LiteLLM reads these provider-native env names,
    # so keep them explicit and set only the keys needed for the configured models.
    OPENROUTER_API_KEY: str | None = os.getenv("OPENROUTER_API_KEY")

    # LiteLLM model settings. Values must include provider prefixes, e.g.
    # "gemini/gemini-2.0-flash", "openai/gpt-5.1", "anthropic/claude-sonnet-4-5",
    # or "openrouter/openai/gpt-4o".
    SERPER_CONTENT_PARSER_MODEL: str = "openrouter/nvidia/nemotron-3-nano-30b-a3b:free"
    SERPER_CONTENT_PARSER_MODEL_CONTEXT_WINDOW: int = 256000 # 256K

    # Gemini Model Settings for Conversation Agent
    CONVERSATION_AGENT_MODEL: str = "openrouter/nvidia/nemotron-3-nano-30b-a3b:free"
    CONVERSATION_AGENT_MODEL_CONTEXT_WINDOW: int = 256000 # 256K

    # Gemini Model Settings for Context Pruning
    CONTEXT_PRUNING_MODEL: str = "openrouter/nvidia/nemotron-3-nano-30b-a3b:free"
    CONTEXT_PRUNING_MODEL_CONTEXT_WINDOW: int = 256000 # 256K

    # Gemini Model Settings for Planner Agent
    PLANNER_AGENT_MODEL: str = "openrouter/poolside/laguna-xs.2:free"
    PLANNER_AGENT_MODEL_CONTEXT_WINDOW: int = 131000 # 131K

    # Gemini Model Settings for Editor Agent
    EDITOR_AGENT_MODEL: str = "openrouter/poolside/laguna-xs.2:free"
    EDITOR_AGENT_MODEL_CONTEXT_WINDOW: int = 131000 # 131K

    # Serper Web Search API key
    SERPER_API_KEY: str = os.getenv("SERPER_API_KEY")
    
    # Rapid API key
    RAPID_API_KEY: str = os.getenv("RAPID_API_KEY")

    # Secret key for JWT Tokens
    SECRET_KEY: str = os.getenv("SECRET_KEY")

    # Email settings
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY")

    # Fallbacks
    FALLBACK_IMAGE: str = "https://images.unsplash.com/photo-1488085061387-422e29b40080?q=80&w=3131&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D"

settings = Settings()
