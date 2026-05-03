from typing import Optional

from google.genai import types

from app.agent.core.runtime import runtime
from app.core.config import settings

from app.logging import get_agent_logger
from app.agent.mcp_server.tools._timeouts import TIMEOUTS
from app.agent.helpers.utils import TOOL_NAME_TO_EVENT_TYPE, ASK_USER_QUESTION_TOOL_NAME
from app.agent.langgraph_runtime.streaming import emit
from app.agent.langgraph_runtime.validator import validate_itinerary_event
from app.agent.langgraph_runtime.collaboration import (
    await_answer_with_heartbeat,
    format_answer_for_llm,
    open_question,
    validate_question_args,
)
from app.services.rate_limiter.rate_limiter import RateLimitExceeded, get_rate_limiter
from app.services.rate_limiter.sku_resolver import resolve_gemini_model_sku

log = get_agent_logger("context_pruning")

# Token-based history pruning.  Trigger pruning when TOTAL context usage
# (system prompt + tool schemas + history) approaches `_PRUNE_THRESHOLD_RATIO`
# of the model's context window; after pruning aim for `_PRUNE_TARGET_RATIO`.
# The first history item (the initial user message) is always preserved — it
# contains the node-specific task prompt.
_PRUNE_THRESHOLD_RATIO = 0.75
_PRUNE_TARGET_RATIO = 0.50
_PRUNE_MAX_ITERS = 8

_MODEL = settings.PLANNER_AGENT_MODEL
_PRUNING_SKU = resolve_gemini_model_sku(settings.CONTEXT_PRUNING_MODEL)

# One-time cache for the static token overhead (system instruction + tool
# schemas).  Keyed by id(config) so each node's config is measured once.
_static_overhead_cache: dict[int, int] = {}


def _estimate_tokens_from_chars(history: list) -> int:
    """Char/4 heuristic — used when count_tokens fails so pruning still fires."""
    total_chars = 0
    for item in history:
        parts = getattr(item, "parts", None) or []
        for p in parts:
            txt = getattr(p, "text", None)
            if isinstance(txt, str):
                total_chars += len(txt)
            fc = getattr(p, "function_call", None)
            if fc is not None:
                try:
                    total_chars += len(str(dict(fc.args or {})))
                except Exception:
                    pass
                total_chars += len(getattr(fc, "name", "") or "")
            fr = getattr(p, "function_response", None)
            if fr is not None:
                try:
                    total_chars += len(str(getattr(fr, "response", "")))
                except Exception:
                    pass
    return total_chars // 3


async def _get_static_overhead(
    client, config: types.GenerateContentConfig
) -> int:
    """
    One-time count of system_instruction + tool-schema tokens.

    Result is cached by ``id(config)`` so subsequent calls for the same
    node config are free.  If the network call fails, falls back to a
    conservative estimate (40 000 tokens — roughly 30-50 MCP tool schemas
    + a multi-KB system prompt).
    """
    key = id(config)
    if key in _static_overhead_cache:
        return _static_overhead_cache[key]
    try:
        resp = await client.aio.models.count_tokens(
            model=_MODEL,
            contents=[" "],
            config=types.GenerateContentConfig(
                system_instruction=config.system_instruction,
                tools=config.tools,
            ),
        )
        overhead = int(getattr(resp, "total_tokens", 0) or 0)
        _static_overhead_cache[key] = overhead
        log.info("Static overhead computed", tokens=overhead)
        return overhead
    except Exception as exc:
        log.warning("Failed to compute static overhead; using 40k fallback", error=str(exc))
        _static_overhead_cache[key] = 40_000
        return 40_000

async def _count_tokens_safe(
    client,
    history: list,
    config: Optional[types.GenerateContentConfig] = None,
) -> Optional[int]:
    """
    Return total tokens for the full request (system + tools + history).

    When *config* is supplied the count includes system_instruction and tool
    schemas — giving an accurate picture of context-window usage.  Falls back
    to char/3 estimate of history + cached static overhead if the SDK call
    fails.
    """
    if not history:
        return 0
    try:
        count_cfg = None
        if config is not None:
            count_cfg = types.GenerateContentConfig(
                system_instruction=config.system_instruction,
                tools=config.tools,
            )
        resp = await client.aio.models.count_tokens(
            model=_MODEL, contents=history, config=count_cfg,
        )
        t = int(getattr(resp, "total_tokens", 0) or 0)
        if t > 0:
            return t
    except Exception as exc:
        log.debug("count_tokens failed; using char estimate", error=str(exc))
    # Fallback: char estimate + cached static overhead (if available).
    est = _estimate_tokens_from_chars(history)
    if config is not None:
        est += _static_overhead_cache.get(id(config), 40_000)
    return est


_RECAP_PROMPT = (
    "You are summarizing intermediate messages from an AI travel-planner's "
    "chat history that are about to be dropped to free context window. "
    "Write a compact recap in <=220 words capturing ONLY information the "
    "planner still needs for later turns: tools called, key facts discovered "
    "(prices, flight numbers, hotel names, place IDs, coordinates, booking "
    "URLs), decisions locked in, and any open loose ends. Preserve exact "
    "numeric values. No preamble, no bullet headers, no meta commentary — "
    "just the recap paragraph."
)


async def _summarize_dropped(dropped: list) -> Optional[str]:
    """
    Use the small pruning model to compress dropped chat items into a short
    recap the planner can reference on later turns. Returns None on any
    failure — caller falls back to drop-without-recap behavior.
    """
    if not dropped or runtime.pruning_client is None:
        return None
    try:
        chunks: list[str] = []
        for item in dropped:
            parts = getattr(item, "parts", None) or []
            role = getattr(item, "role", "") or ""
            for p in parts:
                txt = getattr(p, "text", None)
                if isinstance(txt, str) and txt:
                    chunks.append(f"[{role}] {txt}")
                fc = getattr(p, "function_call", None)
                if fc is not None:
                    try:
                        args_repr = str(dict(fc.args or {}))[:2000]
                    except Exception:
                        args_repr = ""
                    chunks.append(f"[tool_call {getattr(fc, 'name', '')}] {args_repr}")
                fr = getattr(p, "function_response", None)
                if fr is not None:
                    try:
                        resp_repr = str(getattr(fr, "response", ""))[:2000]
                    except Exception:
                        resp_repr = ""
                    chunks.append(f"[tool_response {getattr(fr, 'name', '')}] {resp_repr}")
        blob = "\n".join(chunks)
        if not blob.strip():
            return None
        # Rate-limit gate.
        try:
            await get_rate_limiter().consume(_PRUNING_SKU)
        except RateLimitExceeded as exc:
            log.warning("Pruning model quota exhausted", sku=exc.sku, retry_after=exc.retry_after_seconds)
            return None
        resp = await runtime.pruning_client.aio.models.generate_content(
            model=settings.CONTEXT_PRUNING_MODEL,
            contents=[f"Messages to recap:\n\n{blob}"],
            config=types.GenerateContentConfig(
                system_instruction=_RECAP_PROMPT,
                temperature=0.1,
                max_output_tokens=512,
            ),
        )
        text = getattr(resp, "text", None)
        if isinstance(text, str) and text.strip():
            log.info("Pruning summarization successful", summary_length=len(text.strip()))
            return text.strip()
    except Exception as exc:
        log.warning("Pruning summarization failed", error=str(exc))
    return None


async def _needs_pruning(
    client,
    history: list,
    config: Optional[types.GenerateContentConfig] = None,
) -> bool:
    """Cheap gate: does the current history cross the prune threshold?"""
    if len(history) <= 3:
        return False
    ctx_window = settings.PLANNER_AGENT_MODEL_CONTEXT_WINDOW
    threshold = int(ctx_window * _PRUNE_THRESHOLD_RATIO)
    static_overhead = await _get_static_overhead(client, config) if config else 0
    local_estimate = _estimate_tokens_from_chars(history) + static_overhead
    if local_estimate < int(threshold * 0.8):
        return False
    # Confirm with full network count before committing to a prune.
    total = await _count_tokens_safe(client, history, config=config)
    return (total or local_estimate) >= threshold


async def _prune_history(
    client,
    history: list,
    config: Optional[types.GenerateContentConfig] = None,
) -> tuple[list, int, str | None]:
    """
    Token-aware sliding-window pruning with recap injection.

    Assumes the caller has already confirmed pruning is needed (via
    ``_needs_pruning``) and emitted the "pruning" chunk — this function
    performs the drop, summarizes what it dropped via the small pruning
    model, and injects the recap as a synthetic user note right after
    ``history[0]`` so no context is lost outright.

    Returns ``(new_history, dropped_count, summary_text_or_None)``.
    """
    if len(history) <= 1:
        return history, 0, None

    ctx_window = settings.PLANNER_AGENT_MODEL_CONTEXT_WINDOW
    target = int(ctx_window * _PRUNE_TARGET_RATIO)
    static_overhead = await _get_static_overhead(client, config) if config else 0

    pruned = list(history)
    dropped_acc: list = []
    for _ in range(_PRUNE_MAX_ITERS):
        if len(pruned) <= 3:
            break
        dropped_acc.extend(pruned[1:3])
        pruned = pruned[:1] + pruned[3:]
        if _estimate_tokens_from_chars(pruned) + static_overhead <= target:
            break

    if not dropped_acc:
        log.info("No history dropped. Not pruning further.")
        return history, 0, None

    summary = await _summarize_dropped(dropped_acc)
    if summary:
        try:
            recap_content = types.Content(
                role="user",
                parts=[types.Part.from_text(
                    text=f"[RECAP of earlier messages dropped to free context]\n{summary}"
                )],
            )
            pruned = pruned[:1] + [recap_content] + pruned[1:]
        except Exception as exc:
            log.warning("Failed to inject recap into pruned history", error=str(exc))

    log.info(
        "History pruned",
        pruned_length=len(pruned),
        dropped_count=len(dropped_acc),
        recap_injected=bool(summary),
    )
    return pruned, len(dropped_acc), summary
