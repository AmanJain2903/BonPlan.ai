"""
Structured logger for the BonPlan agent.

Provides context-aware logging that attaches graph_run_id, node_name, and
day_number to every log line, making it easy to trace a single trip's
execution across multiple LangGraph nodes.

Logs are mirrored to:
  - stderr (always) — so they stream in the terminal while a run is live
  - an append-only file at $BONPLAN_LOG_DIR/agent/<YYYY-MM-DD>.log
    (default: backend/logs/agent/<YYYY-MM-DD>.log)
"""
import logging
import json
import os
import sys
import threading
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Optional

# Context variables — set by each LangGraph node at its entry point.
_ctx_run_id: ContextVar[Optional[str]] = ContextVar("run_id", default=None)
_ctx_node: ContextVar[Optional[str]] = ContextVar("node", default=None)
_ctx_day: ContextVar[Optional[int]] = ContextVar("day", default=None)

# ── File sink ────────────────────────────────────────────────────────────────
# Project root = two levels above backend/ (…/BonPlan.ai). Anything relative
# in LOG_ROOT is resolved against it so logs don't depend on where the process
# happened to be launched from.
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
_DEFAULT_LOG_ROOT = os.path.join(_PROJECT_ROOT, "logs")
_env_log_root = os.environ.get("LOG_ROOT")
if _env_log_root:
    _LOG_ROOT = _env_log_root if os.path.isabs(_env_log_root) \
        else os.path.abspath(os.path.join(_PROJECT_ROOT, _env_log_root))
else:
    _LOG_ROOT = _DEFAULT_LOG_ROOT
_log_file_lock = threading.Lock()
_log_file_handle = None
_log_file_date: Optional[str] = None


def _get_log_file(logsName):
    """Return an append-mode file handle rotated daily by YYYY-MM-DD."""
    global _log_file_handle, _log_file_date
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _log_file_handle is not None and _log_file_date == today:
        return _log_file_handle
    with _log_file_lock:
        if _log_file_handle is not None and _log_file_date == today:
            return _log_file_handle
        try:
            _LOG_FILE_ROOT = os.path.join(_LOG_ROOT, logsName)
            os.makedirs(_LOG_FILE_ROOT, exist_ok=True)
            path = os.path.join(_LOG_FILE_ROOT, f"{today}.log")
            if _log_file_handle is not None:
                try:
                    _log_file_handle.close()
                except Exception:
                    pass
            _log_file_handle = open(path, "a", encoding="utf-8")
            _log_file_date = today
        except Exception as e:
            print(f"[logging] Could not open log file: {e}", file=sys.stderr)
            _log_file_handle = None
    return _log_file_handle


def log_file_path(logsName) -> str:
    """Return the current day's log file path (useful for tests/tooling)."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return os.path.join(_LOG_ROOT, logsName, f"{today}.log")


def set_agent_log_context(
    run_id: Optional[str] = None,
    node: Optional[str] = None,
    day: Optional[int] = None,
) -> None:
    """Set context vars for the current async task."""
    if run_id is not None:
        _ctx_run_id.set(run_id)
    if node is not None:
        _ctx_node.set(node)
    if day is not None:
        _ctx_day.set(day)


class AgentLogger:
    """
    Thin structured logger.  Each call emits a JSON line to stderr so it
    doesn't interfere with the SSE response stream on stdout.
    """

    def __init__(self, name: str) -> None:
        self._name = name
        self._logger = logging.getLogger(name)

    def _emit(self, level: str, message: str, **extra: Any) -> None:
        record: dict = {
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
        f = _get_log_file("agent")
        if f is not None:
            try:
                f.write(line + "\n")
                f.flush()
            except Exception:
                pass

    def info(self, message: str, **extra: Any) -> None:
        self._emit("INFO", message, **extra)

    def warning(self, message: str, **extra: Any) -> None:
        self._emit("WARN", message, **extra)

    def error(self, message: str, **extra: Any) -> None:
        self._emit("ERROR", message, **extra)

    def debug(self, message: str, **extra: Any) -> None:
        self._emit("DEBUG", message, **extra)


# Module-level factory — one logger per logical component.
def get_agent_logger(name: str) -> AgentLogger:
    return AgentLogger(name)
