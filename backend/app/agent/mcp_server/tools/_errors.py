# backend/app/agent/mcp_server/tools/_errors.py

"""
Uniform error envelope for MCP tools.

The agent runtime forwards `tool_response` chunks verbatim into the next
model turn, so the `fix_hint` text is what the model reads and reacts to
when deciding how to retry. Keep hints concrete and action-oriented —
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
    return err
