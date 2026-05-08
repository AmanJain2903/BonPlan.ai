"""
Structured logger for the BonPlan backend.

Provides context-aware logging that attaches graph_run_id, node_name, and
day_number to every log line — useful for tracing a trip's execution across
LangGraph nodes — while also serving as the single logging entry point for
every component in the backend.

Each logger writes JSON-line records to its own daily-rotated file under
$BONPLAN_LOG_DIR (default: backend/logs/), inside a subfolder named for the
component. The folder layout mirrors the call sites:

    logs/
      app/<YYYY-MM-DD>.log               ← AppLogger        (app.py / ai.py boot)
      agent/<YYYY-MM-DD>.log             ← AgentLogger      (LangGraph nodes)
      api/<YYYY-MM-DD>.log               ← APILogger        (HTTP endpoints)
      core/<YYYY-MM-DD>.log              ← CoreLogger       (config, redis, …)
      database/<YYYY-MM-DD>.log          ← DatabaseLogger   (models, migrations)
      services/<YYYY-MM-DD>.log          ← ServicesLogger   (generic services)
      services/rate_limiter/<YYYY-MM-DD>.log ← RateLimiterLogger
      mcp/<YYYY-MM-DD>.log               ← MCPLogger        (MCP server + tool calls)
      utils/<YYYY-MM-DD>.log             ← UtilsLogger      (helpers, http client)

Records are also nothing-on-stdout by design: stdout is reserved for the SSE
streaming response. The file is the durable sink; tail it for live runs.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, TextIO

from app.core.config import settings

# ── Context variables ────────────────────────────────────────────────────────
# Set by LangGraph nodes (or any other request handler) so every emit downstream
# carries the same correlation IDs without needing to thread them through args.
_ctx_run_id: ContextVar[Optional[str]] = ContextVar("run_id", default=None)
_ctx_node: ContextVar[Optional[str]] = ContextVar("node", default=None)
_ctx_day: ContextVar[Optional[int]] = ContextVar("day", default=None)


# ── File sink ────────────────────────────────────────────────────────────────
# Project root resolves to …/BonPlan.ai (two levels above this file). Anything
# relative in LOG_ROOT is anchored there so `python -m`, `uvicorn` and tests
# all land in the same place.
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
_env_log_root = settings.LOG_ROOT

_LOG_ROOT = (
    _env_log_root
    if os.path.isabs(_env_log_root)
    else os.path.abspath(os.path.join(_PROJECT_ROOT, _env_log_root))
)


# Per-folder handle cache. Keyed by subdir so AgentLogger and APILogger can
# write concurrently without thrashing a shared file pointer
_log_handles: dict[str, tuple[TextIO, str]] = {}
_log_handles_lock = threading.Lock()

def _get_log_file(logs_subdir: str) -> Optional[TextIO]:
    """Return today's append-mode file handle for `logs_subdir`, rotating on UTC date."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cur = _log_handles.get(logs_subdir)
    if cur is not None and cur[1] == today:
        return cur[0]
    with _log_handles_lock:
        cur = _log_handles.get(logs_subdir)
        if cur is not None and cur[1] == today:
            return cur[0]
        try:
            root = os.path.join(_LOG_ROOT, logs_subdir)
            os.makedirs(root, exist_ok=True)
            path = os.path.join(root, f"{today}.log")
            if cur is not None:
                try:
                    cur[0].close()
                except Exception:
                    pass
            f = open(path, "a", encoding="utf-8")
            _log_handles[logs_subdir] = (f, today)
            return f
        except Exception as e:
            print(f"[logging] Could not open log file ({logs_subdir}): {e}", file=sys.stderr)
            return None


def log_file_path(logs_subdir: str) -> str:
    """Return the current day's log file path for the given subdir (tests/tooling)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return os.path.join(_LOG_ROOT, logs_subdir, f"{today}.log")


# ── Context API ──────────────────────────────────────────────────────────────

def set_agent_log_context(
    run_id: Optional[str] = None,
    node: Optional[str] = None,
    day: Optional[int] = None,
) -> None:
    """Set context vars for the current async task. Used by LangGraph nodes."""
    if run_id is not None:
        _ctx_run_id.set(run_id)
    if node is not None:
        _ctx_node.set(node)
    if day is not None:
        _ctx_day.set(day)


# ── Base logger ──────────────────────────────────────────────────────────────


class BonPlanLogger:
    """
    Shared base for every component logger.

    Subclasses fix `logs_subdir` to the folder under `logs/` they write to, and
    expose info / warning / error / debug. The wire format is one JSON object
    per line — easy to grep, tail, ship to Loki/Datadog/CloudWatch later.
    """

    logs_subdir: str = "misc"  # overridden by every concrete subclass

    def __init__(self, name: str) -> None:
        self._name = name

    def _emit(self, level: str, message: str, **extra: Any) -> None:
        record: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "logger": self._name,
            "msg": message,
        }
        run_id = _ctx_run_id.get()
        node = _ctx_node.get()
        day = _ctx_day.get()
        if run_id:
            record["run_id"] = run_id
        if node:
            record["node"] = node
        if day is not None:
            record["day"] = day
        if extra:
            record.update(extra)
        line = json.dumps(record, default=str)
        # Stderr first — captures even before the file handle is ready, and
        # is what K8s / Cloud Run / Heroku-style platforms actually scrape.
        # We use stderr (not stdout) to keep the SSE response stream clean.
        try:
            print(line, file=sys.stderr, flush=True)
        except Exception:
            pass
        if settings.LOCAL_DEVELOPMENT:
            f = _get_log_file(self.logs_subdir)
            if f is not None:
                try:
                    f.write(line + "\n")
                    f.flush()
                except Exception:
                    # Never let a logging failure take down the request.
                    pass

    def info(self, message: str, **extra: Any) -> None:
        self._emit("INFO", message, **extra)

    def warning(self, message: str, **extra: Any) -> None:
        self._emit("WARN", message, **extra)

    def error(self, message: str, **extra: Any) -> None:
        self._emit("ERROR", message, **extra)

    def debug(self, message: str, **extra: Any) -> None:
        self._emit("DEBUG", message, **extra)

    def exception(self, message: str, **extra: Any) -> None:
        """
        Emit at ERROR level and attach the active exception's repr + traceback.
        Mirrors stdlib `logger.exception()` ergonomics.
        """
        import traceback as _tb
        exc_text = _tb.format_exc()
        if exc_text and exc_text.strip() != "NoneType: None":
            extra = {**extra, "traceback": exc_text}
        self._emit("ERROR", message, **extra)


# ── Concrete loggers ─────────────────────────────────────────────────────────
# Each fixes its subdir. Add more here when a new top-level component shows up.


class AppLogger(BonPlanLogger):
    """app.py / ai.py boot, lifespan, top-level wiring."""
    logs_subdir = "app"


class AgentLogger(BonPlanLogger):
    """LangGraph nodes and the planner runtime."""
    logs_subdir = "agent"


class APILogger(BonPlanLogger):
    """HTTP endpoints (FastAPI routers under app/api and app/agent/api)."""
    logs_subdir = "api"


class CoreLogger(BonPlanLogger):
    """app/core/* — config, redis client, auth wiring."""
    logs_subdir = "core"


class ServicesLogger(BonPlanLogger):
    """app/services/* — generic services (anything not specialized below)."""
    logs_subdir = "services"


class RateLimiterLogger(BonPlanLogger):
    """app/services/rate_limiter/* — nested under services/ to keep noisy
    quota traffic out of the generic services log."""
    logs_subdir = os.path.join("services", "rate_limiter")


class MCPLogger(BonPlanLogger):
    """app/agent/mcp_server/* — every MCP tool error, retry, cache miss, and
    rate-limit branch lands here. Kept in its own top-level folder so the
    high-volume tool traffic doesn't drown the LangGraph agent logs."""
    logs_subdir = "mcp"


class UtilsLogger(BonPlanLogger):
    """app/utils/* — http client, time helpers, shared utilities."""
    logs_subdir = "utils"


# ── Factories ────────────────────────────────────────────────────────────────
# Prefer these over instantiating classes directly — keeps call sites uniform
# and gives us a single place to tweak construction later.


def get_app_logger(name: str) -> AppLogger:
    return AppLogger(name)


def get_agent_logger(name: str) -> AgentLogger:
    return AgentLogger(name)


def get_api_logger(name: str) -> APILogger:
    return APILogger(name)


def get_core_logger(name: str) -> CoreLogger:
    return CoreLogger(name)


def get_services_logger(name: str) -> ServicesLogger:
    return ServicesLogger(name)


def get_rate_limiter_logger(name: str) -> RateLimiterLogger:
    return RateLimiterLogger(name)


def get_mcp_logger(name: str) -> MCPLogger:
    return MCPLogger(name)


def get_utils_logger(name: str) -> UtilsLogger:
    return UtilsLogger(name)
