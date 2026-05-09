# backend/app/agent/mcp_server/tools/_errors.py

"""
Uniform error envelope for MCP tools.

The agent runtime forwards MCP tool results into the next model turn, so the
`fix_hint` text is what the model reads and reacts to when deciding how to
retry. Keep hints concrete and action-oriented —
they should tell the model exactly which parameters to change, not just
what went wrong.

Envelope fields:
- ``error``: one-line human-readable failure summary.
- ``fix_hint``: imperative instruction the model can act on.
- ``status_code`` (optional): upstream HTTP status when available, so the
  agent can distinguish transient errors (5xx) from client errors (4xx).
- any extra keys from ``extra`` merged in (e.g. ``page_length``,
  ``valid_types_sample``, ``invalid_types``) to give structured context.
"""

from typing import Any, Optional

from app.logging import get_mcp_logger

# Single logger funnel for *every* tool error in the MCP layer. The tool name
# itself ends up in the `extra` dict (or is implied by the message), so we
# don't need 12 per-tool loggers — one centralised sink is easier to grep.
_logger = get_mcp_logger("tool_error")


def tool_error(
    message: str,
    *,
    fix_hint: str,
    status_code: Optional[int] = None,
    extra: Optional[dict[str, Any]] = None,
) -> dict:
    err: dict[str, Any] = {"error": message, "fix_hint": fix_hint}
    if status_code is not None:
        err["status_code"] = status_code
    if extra:
        # Never let `extra` overwrite the canonical envelope keys.
        for k, v in extra.items():
            if k not in err:
                err[k] = v
    # Mirror every tool error into the MCP log so we have a record of which
    # tools failed, why, and with what context — independent of whether the
    # model chooses to surface the failure to the user. When tool_error is
    # called from inside an `except` block, `.exception()` will capture the
    # traceback automatically; outside an except block it falls back to
    # plain `.error()/.warning()`.
    try:
        log_extra = {k: v for k, v in err.items() if k not in ("error", "fix_hint")}
        import sys as _sys
        active_exc = _sys.exc_info()[0] is not None
        if status_code and status_code >= 500:
            if active_exc:
                _logger.exception(message, **log_extra)
            else:
                _logger.error(message, **log_extra)
        elif status_code and status_code == 429:
            _logger.warning(message, **log_extra)
        else:
            if active_exc:
                # Validation / 4xx with a live exception — keep the
                # traceback, but at WARN level since it's typically
                # caller-correctable.
                import traceback as _tb
                tb_text = _tb.format_exc()
                if tb_text and tb_text.strip() != "NoneType: None":
                    log_extra = {**log_extra, "traceback": tb_text}
            _logger.warning(message, **log_extra)
    except Exception:
        pass
    return err
