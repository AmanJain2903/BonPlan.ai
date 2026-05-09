"""
Structured logger for the BonPlan backend.

Provides context-aware logging that attaches graph_run_id, node_name, and
day_number to every log line — useful for tracing a trip's execution across
LangGraph nodes — while also serving as the single logging entry point for
every component in the backend.

In local development, each logger writes JSON-line records to its own
daily-rotated file under $BONPLAN_LOG_DIR (default: backend/logs/), inside a
subfolder named for the component. In non-local environments, records are
buffered and streamed to Grafana Loki using the Grafana credentials configured
in app.core.config.

The folder layout for local files mirrors the call sites:

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
streaming response. Stderr mirrors every emit for platform-native log capture
and as a fallback if Loki delivery fails.
"""

from __future__ import annotations

import atexit
import json
import os
import queue
import sys
import threading
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Optional, TextIO

import httpx

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

_LOKI_BATCH_SIZE = 100
_LOKI_BATCH_INTERVAL_SECONDS = 1.0
_LOKI_HTTP_TIMEOUT_SECONDS = 5.0
_LOKI_QUEUE_MAX_SIZE = 10_000

_loki_sender: Optional["LokiSender"] = None
_loki_sender_lock = threading.Lock()
_warnings_emitted: set[str] = set()

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


def _warn_once(key: str, message: str) -> None:
    with _loki_sender_lock:
        if key in _warnings_emitted:
            return
        _warnings_emitted.add(key)
    try:
        print(message, file=sys.stderr, flush=True)
    except Exception:
        pass


def _normalize_loki_url(url: str) -> str:
    """Accept either a Loki base URL or the full push endpoint."""
    clean = url.rstrip("/")
    if clean.endswith("/loki/api/v1/push"):
        return clean
    return f"{clean}/loki/api/v1/push"


def _environment_name() -> str:
    return "local" if settings.LOCAL_DEVELOPMENT else "production"


def _write_local_record(logs_subdir: str, line: str) -> None:
    f = _get_log_file(logs_subdir)
    if f is not None:
        try:
            f.write(line + "\n")
            f.flush()
        except Exception:
            # Never let a logging failure take down the request.
            pass


def _build_loki_labels(record: dict[str, Any], logs_subdir: str) -> dict[str, str]:
    return {
        "service": "bonplan-backend",
        "project": settings.PROJECT_NAME,
        "environment": record["environment"],
        "component": logs_subdir.replace(os.sep, "_"),
        "logger": str(record["logger"]),
        "level": str(record["level"]).lower(),
    }


class LokiSender:
    """Background Loki shipper that keeps HTTP I/O off the request path."""

    def __init__(self, url: str, username: Optional[str], token: Optional[str]) -> None:
        headers = {"Content-Type": "application/json"}
        auth: Any = None
        if username and token:
            auth = (username, token)
        elif token:
            headers["Authorization"] = f"Bearer {token}"

        self._url = _normalize_loki_url(url)
        self._client = httpx.Client(timeout=_LOKI_HTTP_TIMEOUT_SECONDS, headers=headers, auth=auth)
        self._queue: queue.Queue[tuple[dict[str, str], str, str]] = queue.Queue(maxsize=_LOKI_QUEUE_MAX_SIZE)
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._run, name="bonplan-loki", daemon=True)
        self._last_error_ts = 0.0
        self._worker.start()

    def emit(self, record: dict[str, Any], logs_subdir: str) -> None:
        line = json.dumps(record, default=str)
        item = (_build_loki_labels(record, logs_subdir), str(time.time_ns()), line)
        try:
            self._queue.put_nowait(item)
        except queue.Full:
            self._warn_rate_limited("Loki queue is full; dropping log records.")

    def shutdown(self, timeout_seconds: float = 5.0) -> None:
        self._stop_event.set()
        self._worker.join(timeout_seconds)
        if self._worker.is_alive():
            self._warn_rate_limited("Loki worker did not stop cleanly before timeout.")
        try:
            self._client.close()
        except Exception:
            pass

    def _run(self) -> None:
        pending: list[tuple[dict[str, str], str, str]] = []
        next_flush_at = time.monotonic() + _LOKI_BATCH_INTERVAL_SECONDS
        while not self._stop_event.is_set() or not self._queue.empty() or pending:
            timeout = max(0.0, next_flush_at - time.monotonic())
            try:
                pending.append(self._queue.get(timeout=timeout))
            except queue.Empty:
                pass

            should_flush = False
            if pending and len(pending) >= _LOKI_BATCH_SIZE:
                should_flush = True
            elif pending and time.monotonic() >= next_flush_at:
                should_flush = True

            if should_flush:
                self._flush(pending)
                pending = []
                next_flush_at = time.monotonic() + _LOKI_BATCH_INTERVAL_SECONDS

        if pending:
            self._flush(pending)

    def _flush(self, items: list[tuple[dict[str, str], str, str]]) -> None:
        streams: dict[str, dict[str, Any]] = {}
        for labels, ts_ns, line in items:
            key = json.dumps(labels, sort_keys=True, separators=(",", ":"))
            stream = streams.setdefault(key, {"stream": labels, "values": []})
            stream["values"].append([ts_ns, line])

        try:
            response = self._client.post(self._url, json={"streams": list(streams.values())})
            response.raise_for_status()
        except Exception as exc:
            self._warn_rate_limited(f"Loki push failed: {exc}")

    def _warn_rate_limited(self, message: str) -> None:
        now = time.monotonic()
        if now - self._last_error_ts < 30:
            return
        self._last_error_ts = now
        try:
            print(f"[logging] {message}", file=sys.stderr, flush=True)
        except Exception:
            pass


def _get_loki_sender() -> Optional[LokiSender]:
    if settings.LOCAL_DEVELOPMENT:
        return None

    if not settings.GRAFANA_LOKI_URL:
        _warn_once(
            "missing-loki-url",
            "[logging] GRAFANA_LOKI_URL is not configured; production Loki logging is disabled.",
        )
        return None

    global _loki_sender
    if _loki_sender is not None:
        return _loki_sender

    with _loki_sender_lock:
        if _loki_sender is not None:
            return _loki_sender
        _loki_sender = LokiSender(
            url=settings.GRAFANA_LOKI_URL,
            username=settings.GRAFANA_LOKI_USER,
            token=settings.GRAFANA_LOKI_TOKEN,
        )
        return _loki_sender


def shutdown_logging(timeout_seconds: float = 5.0) -> None:
    global _loki_sender
    with _loki_sender_lock:
        sender = _loki_sender
        _loki_sender = None
    if sender is not None:
        sender.shutdown(timeout_seconds=timeout_seconds)


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
            "environment": _environment_name(),
            "component": self.logs_subdir,
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
            _write_local_record(self.logs_subdir, line)
            return

        sender = _get_loki_sender()
        if sender is not None:
            sender.emit(record, self.logs_subdir)

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


atexit.register(shutdown_logging)
