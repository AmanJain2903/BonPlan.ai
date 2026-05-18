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

    LOCAL_DEVELOPMENT: bool = os.getenv("LOCAL_DEVELOPMENT", "false").lower() == "true"

    # Deployment settings
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    AGENT_URL: str = os.getenv("AGENT_URL", "http://localhost:8001")
    MCP_URL: str = os.getenv("MCP_URL", "http://localhost:8002")
    MCP_SSE_PATH: str = os.getenv("MCP_SSE_PATH", "/mcp/sse")
    MCP_CONNECT_TIMEOUT_SECONDS: float = os.getenv("MCP_CONNECT_TIMEOUT_SECONDS", "10") # 10 seconds
    MCP_STARTUP_MAX_WAIT_SECONDS: float = os.getenv("MCP_STARTUP_MAX_WAIT_SECONDS", "300") # 5 minutes
    MCP_STARTUP_INITIAL_BACKOFF_SECONDS: float = os.getenv("MCP_STARTUP_INITIAL_BACKOFF_SECONDS", "1") # 1 second
    MCP_STARTUP_MAX_BACKOFF_SECONDS: float = os.getenv("MCP_STARTUP_MAX_BACKOFF_SECONDS", "30") # 30 seconds
    
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # Logging settings
    LOG_ROOT: str = "backend/logs"

    # Project settings
    PROJECT_NAME: str = "BonPlan.ai"
    AGENT_NAME: str = "BonPlan.ai - Agent"
    MCP_NAME: str = "BonPlan.ai - MCP"
    PROJECT_VERSION: str = os.getenv("PROJECT_VERSION", "v1.0.0") # Version is not set in environment for production build. Set fallback for the production build. Local and Staging uses the Environment Variable.
    AGENT_VERSION: str = os.getenv("AGENT_VERSION", "v1.0.0") # Version is not set in environment for production build. Set fallback for the production build. Local and Staging uses the Environment Variable.
    MCP_VERSION: str = os.getenv("MCP_VERSION", "v1.0.0")

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
    
    # Cloudflare R2 settings (prod only — None in local dev)
    CLOUDFLARE_R2_PHOTO_CACHE_BASE_URL: str | None = os.getenv("CLOUDFLARE_R2_PHOTO_CACHE_BASE_URL")
    CLOUDFLARE_R2__PHOTO_CACHE_BUCKET_NAME: str | None = os.getenv("CLOUDFLARE_R2_PHOTO_CACHE_BUCKET_NAME")
    CLOUDFLARE_R2_ENDPOINT_URL: str | None = os.getenv("CLOUDFLARE_R2_ENDPOINT_URL")
    CLOUDFLARE_R2_ACCESS_KEY_ID: str | None = os.getenv("CLOUDFLARE_R2_ACCESS_KEY_ID")
    CLOUDFLARE_R2_SECRET_ACCESS_KEY: str | None = os.getenv("CLOUDFLARE_R2_SECRET_ACCESS_KEY")

    # Redis settings
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Redis Rate Limiter settings
    REDIS_RATE_LIMIT_PREFIX: str = "rl"
    RATE_LIMITER_MODE: str = os.getenv("RATE_LIMITER_MODE", "strict") # "lenient" in local development. "strict" in staging and production.
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
    SERPER_CONTENT_PARSER_MODEL: str = "gemini/gemini-2.5-flash-lite"
    SERPER_CONTENT_PARSER_MODEL_CONTEXT_WINDOW: int = 1048576 # 1M

    # Gemini Model Settings for Conversation Agent
    CONVERSATION_AGENT_MODEL: str = "gemini/gemini-2.5-flash-lite"
    CONVERSATION_AGENT_MODEL_CONTEXT_WINDOW: int = 1048576 # 1M

    # Gemini Model Settings for Context Pruning
    CONTEXT_PRUNING_MODEL: str = "gemini/gemini-2.5-flash-lite"
    CONTEXT_PRUNING_MODEL_CONTEXT_WINDOW: int = 1048576 # 1M

    # Gemini Model Settings for Planner Agent
    PLANNER_AGENT_MODEL: str = "gemini/gemini-2.5-flash"
    PLANNER_AGENT_MODEL_CONTEXT_WINDOW: int = 1048576 # 1M
    # Base turn budget per day-planner invocation. Each smart anchor on the day
    # adds PLANNER_MAX_TURNS_PER_ANCHOR extra turns. Close-pass runs are capped
    # at PLANNER_MAX_TURNS_CLOSE_PASS regardless.
    PLANNER_MAX_TURNS_BASE: int = int(os.getenv("PLANNER_MAX_TURNS_BASE", "65"))
    PLANNER_MAX_TURNS_PER_ANCHOR: int = int(os.getenv("PLANNER_MAX_TURNS_PER_ANCHOR", "8"))
    PLANNER_MAX_TURNS_CLOSE_PASS: int = int(os.getenv("PLANNER_MAX_TURNS_CLOSE_PASS", "25"))
    PLANNER_MAX_TURN_CAP_RETRIES: int = int(os.getenv("PLANNER_MAX_TURN_CAP_RETRIES", "1"))

    FAST_PLANNER_AGENT_MODEL: str = "gemini/gemini-2.5-flash-lite"
    FAST_PLANNER_AGENT_MODEL_CONTEXT_WINDOW: int = 1048576 # 1M

    # Gemini Model Settings for Editor Agent
    EDITOR_AGENT_MODEL: str = "gemini/gemini-2.5-flash"
    EDITOR_AGENT_MODEL_CONTEXT_WINDOW: int = 1048576 # 1M

    FAST_EDITOR_AGENT_MODEL: str = "gemini/gemini-2.5-flash-lite"
    FAST_EDITOR_AGENT_MODEL_CONTEXT_WINDOW: int = 1048576 # 1M

    def get_planner_agent_model(self, use_fast_model: bool = False) -> tuple[str, int]:
        if use_fast_model:
            return self.FAST_PLANNER_AGENT_MODEL, self.FAST_PLANNER_AGENT_MODEL_CONTEXT_WINDOW
        return self.PLANNER_AGENT_MODEL, self.PLANNER_AGENT_MODEL_CONTEXT_WINDOW

    def get_editor_agent_model(self, use_fast_model: bool = False) -> tuple[str, int]:
        if use_fast_model:
            return self.FAST_EDITOR_AGENT_MODEL, self.FAST_EDITOR_AGENT_MODEL_CONTEXT_WINDOW
        return self.EDITOR_AGENT_MODEL, self.EDITOR_AGENT_MODEL_CONTEXT_WINDOW

    # Serper Web Search API key
    SERPER_API_KEY: str = os.getenv("SERPER_API_KEY")
    
    # Rapid API key
    RAPID_API_KEY: str = os.getenv("RAPID_API_KEY")

    # Secret key for JWT Tokens
    SECRET_KEY: str = os.getenv("SECRET_KEY")

    # Email settings
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY")

    # HTTP client settings
    HTTP_USER_AGENT: str = os.getenv(
        "HTTP_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )

    # Fallbacks
    FALLBACK_IMAGE: str = "https://images.unsplash.com/photo-1488085061387-422e29b40080?q=80&w=3131&auto=format&fit=crop&ixlib=rb-4.1.0&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D"

settings = Settings()
