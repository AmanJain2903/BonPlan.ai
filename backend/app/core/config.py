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

def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_litellm_model_name(value: str) -> str:
    value = value.strip()
    if "/" in value:
        return value
    if value.startswith(("gemini-", "gemma-")):
        return f"gemini/{value}"
    return value


def _litellm_model(env_name: str, default: str) -> str:
    return _normalize_litellm_model_name(os.getenv(env_name, default))


class Settings(BaseSettings):

    # Deployment settings
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    AGENT_URL: str = os.getenv("AGENT_URL", "http://localhost:8001")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # Logging settings
    LOG_ROOT: str = os.getenv("LOG_ROOT", "backend/logs")

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

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Redis settings
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Redis Rate Limiter settings
    REDIS_RATE_LIMIT_PREFIX: str = "rl"
    RATE_LIMITER_MODE: str = "lenient" # "lenient" (default) — allow the call, log the failure. "strict" — treat as rate-limited (raise). In staging and production, set to "strict".
    RATE_LIMITER_CONFIG_TTL_SECONDS: int = "60"
    RATE_LIMITER_RESET_TZ: str = "America/Los_Angeles"

    # Google Cloud Platform settings
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY")

    # LiteLLM provider API keys. LiteLLM reads these provider-native env names,
    # so keep them explicit and set only the keys needed for the configured
    # models. Existing GEMINI_API_KEY remains supported for Google AI Studio.
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
    GOOGLE_API_KEY: str | None = os.getenv("GOOGLE_API_KEY")
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    OPENAI_API_BASE: str | None = os.getenv("OPENAI_API_BASE")
    ANTHROPIC_API_KEY: str | None = os.getenv("ANTHROPIC_API_KEY")
    ANTHROPIC_API_BASE: str | None = os.getenv("ANTHROPIC_API_BASE")
    OPENROUTER_API_KEY: str | None = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_API_BASE: str | None = os.getenv("OPENROUTER_API_BASE")
    OR_SITE_URL: str | None = os.getenv("OR_SITE_URL")
    OR_APP_NAME: str | None = os.getenv("OR_APP_NAME")
    XAI_API_KEY: str | None = os.getenv("XAI_API_KEY")
    GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
    TOGETHERAI_API_KEY: str | None = os.getenv("TOGETHERAI_API_KEY")
    MISTRAL_API_KEY: str | None = os.getenv("MISTRAL_API_KEY")
    COHERE_API_KEY: str | None = os.getenv("COHERE_API_KEY")
    AZURE_API_KEY: str | None = os.getenv("AZURE_API_KEY")
    AZURE_API_BASE: str | None = os.getenv("AZURE_API_BASE")
    AZURE_API_VERSION: str | None = os.getenv("AZURE_API_VERSION")
    VERTEXAI_PROJECT: str | None = os.getenv("VERTEXAI_PROJECT")
    VERTEXAI_LOCATION: str | None = os.getenv("VERTEXAI_LOCATION")
    LITELLM_API_KEY: str | None = os.getenv("LITELLM_API_KEY")
    LITELLM_API_BASE: str | None = os.getenv("LITELLM_API_BASE")
    LITELLM_DROP_UNSUPPORTED_PARAMS: bool = _env_bool("LITELLM_DROP_UNSUPPORTED_PARAMS", True)
    LITELLM_LOCAL_MODEL_COST_MAP: bool = _env_bool("LITELLM_LOCAL_MODEL_COST_MAP", True)
    LITELLM_VERBOSE: bool = _env_bool("LITELLM_VERBOSE", False)

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

    @field_validator(
        "SERPER_CONTENT_PARSER_MODEL",
        "CONVERSATION_AGENT_MODEL",
        "PLANNER_AGENT_MODEL",
        "CONTEXT_PRUNING_MODEL",
        mode="before",
    )
    @classmethod
    def _normalize_model_env(cls, value: str) -> str:
        return _normalize_litellm_model_name(str(value or ""))

    # Serper Web Search API key
    SERPER_API_KEY: str = os.getenv("SERPER_API_KEY")
    
    # Rapid API key
    RAPID_API_KEY: str = os.getenv("RAPID_API_KEY")

    # Secret key for JWT Tokens
    SECRET_KEY: str = os.getenv("SECRET_KEY")

    # Email settings
    SENDER_EMAIL: str = os.getenv("SENDER_EMAIL")
    GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD")

    # Fallbacks
    FALLBACK_IMAGE: str = os.getenv("FALLBACK_IMAGE", "https://images.unsplash.com/photo-1488085061387-422e29b40080?q=80&w=3131&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D")

settings = Settings()
