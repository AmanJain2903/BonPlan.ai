"""
Google GenAI chat loop for LangGraph nodes.

`run_chat_loop` encapsulates:
  - Streaming from the GenAI API
  - MALFORMED_FUNCTION_CALL / transient-error retry (ported from solo_planner.py)
  - Sliding-window history pruning (keep last WINDOW_TURNS turns)
  - Tool dispatch: add_*_event → validator → emit;  everything else → MCP
  - Chunk emission via streaming.emit()

Each LangGraph node calls `run_chat_loop(...)` with a node-specific initial
message and receives a `ChatResult` back.
"""
import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Optional

from google.genai import types

from app.agent.core.runtime import runtime
from app.core.config import settings

from app.logging import get_agent_logger
from app.agent.mcp_server.tools._timeouts import TIMEOUTS
from app.agent.helpers.utils import TOOL_NAME_TO_EVENT_TYPE
from app.agent.langgraph_runtime.streaming import emit
from app.agent.langgraph_runtime.validator import validate_itinerary_event

log = get_agent_logger("gemini_adapter")

_MODEL = settings.PLANNER_AGENT_MODEL


# Per-tool cap on how many characters of a tool response get forwarded to the
# model on the next turn. Uncapped responses (search_hotels / search_places /
# search_flights can each be 30-50 KB) balloon the model's input on every
# subsequent turn and are the #1 driver of post-tool-call "halts" (high TTFT
# on large context).
_TOOL_RESPONSE_CAPS: dict[str, int] = {
    # Heavy search tools — many results, each big. 12 KB is roughly 8-12 items.
    "search_hotels": 12000,
    "search_places": 8000,
    "search_places_nearby": 8000,
    "search_flights": 12000,
    "search_multi_city_flights": 12000,
    "get_next_flights": 12000,
    "search_rental_cars": 12000,
    # Content scrapes — already trimmed server-side to 4 KB, but defend again.
    "search_web": 6000,
    "get_content_from_url": 5000,
    "get_place_info": 8000,
}
# Default cap for any tool not in the map above. Geocoding / routing / timezone
# responses are small, so this is mostly a safety floor.
_DEFAULT_RESPONSE_CAP = 8000


def _is_event_tool(name: str) -> bool:
    """True for both the legacy monolithic tool and the per-type tools."""
    return name == "add_itinerary_event" or name in TOOL_NAME_TO_EVENT_TYPE


def _coerce_event_args(tool_name: str, raw_args: dict) -> dict:
    """
    Map a per-type tool call back into a unified AddItineraryEvent payload.

    For single-event tools (e.g. add_flight_takeoff_event) we inject the
    event_type the tool name implies, overriding anything the model sent so
    mismatches can't slip through.
    For multi-event tools (add_activity_or_dining_event) we trust the model's
    event_type value since both options are valid.
    """
    args = dict(raw_args or {})
    if tool_name == "add_itinerary_event":
        return args
    fixed = TOOL_NAME_TO_EVENT_TYPE.get(tool_name)
    if fixed is not None:
        args["event_type"] = fixed
    return args

# Token-based history pruning.  Trigger pruning when TOTAL context usage
# (system prompt + tool schemas + history) approaches `_PRUNE_THRESHOLD_RATIO`
# of the model's context window; after pruning aim for `_PRUNE_TARGET_RATIO`.
# The first history item (the initial user message) is always preserved — it
# contains the node-specific task prompt.
_PRUNE_THRESHOLD_RATIO = 0.75
_PRUNE_TARGET_RATIO = 0.50
_PRUNE_MAX_ITERS = 8

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
            contents=[],
            config=types.CountTokensConfig(
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
            count_cfg = types.CountTokensConfig(
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

@dataclass
class ChatResult:
    success: bool
    next_event_number: int
    is_complete: bool          # True if END event was emitted
    error: Optional[str] = None
    last_text: Optional[str] = None  # last non-thought text chunk emitted by the model
    emitted_events: list = None  # events successfully emitted during this chat loop


async def run_chat_loop(
    *,
    initial_message: Any,
    config: types.GenerateContentConfig,
    node_name: str,
    next_event_number: int,
    current_day: int = 0,
    total_days: int = 1,
    mode: str = "autonomous",
    is_resuming: bool = False,
    prior_events: Optional[list] = None,
    cancellation_callback: Optional[Callable[[], Coroutine]] = None,
    stop_after_start: bool = False,   # research node: stop once START is emitted
    require_end: bool = True,         # finalizer: True (END mandatory); day planner: False
) -> ChatResult:
    """
    Run one phase of the planner chat.

    Parameters
    ----------
    initial_message : str or list[types.Part]
        The first user message for this phase.
    config : types.GenerateContentConfig
        Model config including tool declarations.
    node_name : str
        Used for structured log context.
    next_event_number : int
        Counter for event_number assignment (overrides whatever the model sends).
    mode : str
        "autonomous" | "collaborative" | "editing"
    cancellation_callback : async callable -> bool, optional
        Called before each turn; return True to cancel.
    stop_after_start : bool
        If True, return after a START event is successfully emitted (research phase).
    """
    client = runtime.genai_client
    session = runtime.mcp_session

    async def _is_cancelled() -> bool:
        if cancellation_callback is None:
            return False
        try:
            return await cancellation_callback()
        except Exception as e:
            log.warning("Cancellation callback raised", node=node_name, error=str(e))
            return False

    chat = client.aio.chats.create(model=_MODEL, config=config)

    # Baseline Content capturing the initial_message. Used on turn-1
    # MAX_TOKENS/MALFORMED rebuilds where `chat.get_history()` is still empty
    # (the runaway turn never made it into history) — without this, rebuilding
    # would strip the node-specific task prompt (prior_events, research_facts,
    # open bookings, etc.) and the nudge message would land in a chat with
    # zero context.
    def _initial_message_as_content(msg: Any) -> Optional[types.Content]:
        try:
            if isinstance(msg, str):
                return types.Content(role="user", parts=[types.Part.from_text(text=msg)])
            if isinstance(msg, list):
                return types.Content(role="user", parts=list(msg))
        except Exception:
            pass
        return None

    _initial_baseline_content = _initial_message_as_content(initial_message)

    def _baseline_history() -> list:
        return [_initial_baseline_content] if _initial_baseline_content else []

    current_message: Any = initial_message
    is_complete = False
    start_emitted = False
    # Running list of events emitted within this chat loop. Combined with
    # `prior_events` (from persisted state) to feed the placement validator.
    session_events: list = []
    _all_prior_events = list(prior_events or [])
    last_text_buffer: str = ""
    pending_turn_text: str = ""

    max_turn_retries = 3
    turn_retries = 0
    max_turns = 50
    turn_count = 0

    while True:
        if await _is_cancelled():
            log.info("Chat loop cancelled", node=node_name)
            return ChatResult(emitted_events=list(session_events),last_text=last_text_buffer, success=False, next_event_number=next_event_number,
                              is_complete=is_complete, error="Cancelled")

        if turn_count >= max_turns:
            log.error("Node turn cap reached", node=node_name, turns=turn_count)
            emit({"type": "error", "content": f"Node '{node_name}' exceeded turn budget."})
            return ChatResult(emitted_events=list(session_events),last_text=last_text_buffer, success=False, next_event_number=next_event_number,
                              is_complete=is_complete, error="Turn cap reached")

        turn_count += 1
        #   - total attempts per turn capped at 3
        #   - 429 / 503 / 500  → transient, retry with 2 → 4 → 8 s backoff
        #   - "context length" or "INVALID_ARGUMENT" 400s → non-retryable
        #   - anything else → surface immediately
        max_retries = 3
        retry_delay = 2
        retry_exhausted_error: Optional[str] = None

        try:
            history_snapshot = list(chat.get_history())
        except Exception:
            history_snapshot = []

        active_tool_calls: list = []
        last_chunk = None
        stream_ok = False
        pending_turn_text = ""

        for attempt in range(max_retries):
            active_tool_calls = []
            last_chunk = None
            pending_turn_text = ""

            try:
                _turn_started = time.monotonic()
                _first_chunk_at: Optional[float] = None
                response_stream = await chat.send_message_stream(current_message)

                async for chunk in response_stream:
                    if _first_chunk_at is None:
                        _first_chunk_at = time.monotonic()
                    last_chunk = chunk

                    parts = (
                        chunk.candidates[0].content.parts
                        if (
                            chunk.candidates
                            and chunk.candidates[0].content
                            and chunk.candidates[0].content.parts
                        )
                        else []
                    )

                    for part in parts:
                        if isinstance(part.text, str) and part.text:
                            is_thought = bool(getattr(part, "thought", False))
                            if is_thought:
                                emit({"type": "thinking", "content": part.text})
                            elif is_complete:
                                emit({"type": "summary", "content": part.text})
                            else:
                                # Narrative text the model produced BEFORE a tool
                                # call. We don't surface this to the user — the
                                # user only cares about events and the final
                                # summary. Emitting it as a visible chunk just
                                # confuses the UI.
                                pending_turn_text += part.text
                            continue

                        if part.function_call:
                            fc = part.function_call
                            call_id = str(uuid.uuid4())

                            if _is_event_tool(fc.name):
                                args = _coerce_event_args(fc.name, fc.args or {})
                                et = args.get("event_type")
                                # Event numbering is deterministic:
                                #   START → day=0, event=0
                                #   END   → day=-1, event=-1
                                #   Others → counter-assigned, UNLESS the model
                                #           supplied a (day_number, event_number)
                                #           that matches an already-emitted event
                                #           — that is an overwrite (the frontend
                                #           dedupes by these two fields).
                                is_replacement = False
                                replacement_index = None
                                replacement_in_session = False
                                if et == "START":
                                    args["day_number"] = 0
                                    args["event_number"] = 0
                                elif et == "END":
                                    args["day_number"] = -1
                                    args["event_number"] = -1
                                else:
                                    m_day = args.get("day_number")
                                    m_evnum = args.get("event_number")
                                    if isinstance(m_day, int) and isinstance(m_evnum, int):
                                        for idx, e in enumerate(session_events):
                                            if (
                                                e.get("day_number") == m_day
                                                and e.get("event_number") == m_evnum
                                            ):
                                                is_replacement = True
                                                replacement_index = idx
                                                replacement_in_session = True
                                                break
                                        if not is_replacement:
                                            for idx, e in enumerate(_all_prior_events):
                                                if (
                                                    e.get("day_number") == m_day
                                                    and e.get("event_number") == m_evnum
                                                ):
                                                    is_replacement = True
                                                    replacement_index = idx
                                                    break
                                    if not is_replacement:
                                        args["event_number"] = next_event_number
                                        # Force day_number to current_day so the
                                        # model can't hallucinate a wrong day.
                                        if current_day > 0:
                                            args["day_number"] = current_day

                                # For replacements, validate placement as if the
                                # event were being inserted at its original slot
                                # — strip any events at or after that position
                                # from the prior list so the rules compare
                                # against the correct predecessor.
                                combined_prior = _all_prior_events + session_events
                                if is_replacement:
                                    combined_prior = [
                                        e for e in combined_prior
                                        if not (
                                            e.get("day_number") == args.get("day_number")
                                            and e.get("event_number") == args.get("event_number")
                                        )
                                    ]
                                    cutoff_day = args.get("day_number")
                                    cutoff_evnum = args.get("event_number")
                                    combined_prior = [
                                        e for e in combined_prior
                                        if not (
                                            e.get("day_number") == cutoff_day
                                            and isinstance(e.get("event_number"), int)
                                            and e.get("event_number") > cutoff_evnum
                                        )
                                    ]

                                validation_error, coerced_args = await validate_itinerary_event(
                                    args,
                                    mode=mode,
                                    is_resuming=is_resuming,
                                    prior_events=combined_prior,
                                    current_day=current_day,
                                    total_days=total_days,
                                    next_event_number=next_event_number,
                                )
                                active_tool_calls.append((call_id, fc, validation_error, coerced_args))

                                if validation_error is None:
                                    ev_type = coerced_args.get("event_type")
                                    if ev_type == "END":
                                        is_complete = True
                                    elif ev_type == "START":
                                        start_emitted = True
                                    elif is_replacement:
                                        # Overwrite in place; do NOT bump counter.
                                        if replacement_in_session:
                                            session_events[replacement_index] = coerced_args
                                        else:
                                            _all_prior_events[replacement_index] = coerced_args
                                    else:
                                        next_event_number += 1
                                        session_events.append(coerced_args)
                                    if ev_type in ("END", "START"):
                                        session_events.append(coerced_args)
                                    emit({
                                        "type": "event",
                                        "data": coerced_args,
                                        "call_id": call_id,
                                    })
                            else:
                                active_tool_calls.append((call_id, fc, None, None))
                                emit({
                                    "type": "tool_call",
                                    "tool_name": fc.name,
                                    "args": dict(fc.args or {}),
                                    "call_id": call_id,
                                })

                    if await _is_cancelled():
                        log.info("Chat loop cancelled mid-stream", node=node_name)
                        return ChatResult(emitted_events=list(session_events),
                            success=False, next_event_number=next_event_number,
                            is_complete=is_complete, error="Cancelled mid-stream"
                        )

                stream_ok = True
                if pending_turn_text.strip():
                    last_text_buffer = pending_turn_text
                _turn_total = time.monotonic() - _turn_started
                _ttft = (_first_chunk_at - _turn_started) if _first_chunk_at else None
                log.info(
                    "Model turn done",
                    node=node_name,
                    turn=turn_count,
                    ttft_s=round(_ttft, 2) if _ttft is not None else None,
                    total_s=round(_turn_total, 2),
                    tool_calls=len([p for p in (active_tool_calls or [])]),
                )
                break

            except asyncio.CancelledError:
                log.info("Stream cancelled", node=node_name)
                raise

            except Exception as e:
                err_str = str(e)
                err_lower = err_str.lower()

                is_context_error = (
                    "context length" in err_lower
                    or "context window" in err_lower
                    or "maximum tokens" in err_lower
                    or "input is too long" in err_lower
                )
                is_invalid_arg = (
                    "invalid_argument" in err_lower
                    or "400 " in err_str
                )
                is_retryable = (
                    not is_context_error
                    and not is_invalid_arg
                    and any(code in err_str for code in ("503", "429", "500"))
                )

                if is_retryable and attempt < max_retries - 1:
                    log.info(f"Retryable error occured", node=node_name, attempt=attempt, error=err_str)
                    emit({
                        "type": "system",
                        "content": f"Transient upstream error. Retrying in {retry_delay}s... "
                                   f"(attempt {attempt + 1}/{max_retries})",
                        "error": err_str,
                    })
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 8)  # ceiling 8s
                    try:
                        chat = client.aio.chats.create(
                            model=_MODEL, config=config,
                            history=history_snapshot,
                        )
                        log.info(f"Successfully rebuilt chat", node=node_name, attempt=attempt)
                    except Exception as rebuild_err:
                        retry_exhausted_error = f"Failed to rebuild chat: {rebuild_err}"
                        log.error(f"Failed to rebuild chat", node=node_name, attempt=attempt, error=rebuild_err)
                        break
                    continue

                if is_context_error:
                    retry_exhausted_error = (
                        f"Context-length error — not retrying. "
                        f"History size was {len(history_snapshot)} items. {err_str}"
                    )
                    log.error(f"Context-length error", node=node_name, history_size=len(history_snapshot), error=err_str)
                else:
                    retry_exhausted_error = err_str
                    log.error(f"Terminal stream error", node=node_name, error=err_str)
                break

        if not stream_ok:
            err_msg = retry_exhausted_error or "Unknown streaming error."
            log.error("Terminal stream error", node=node_name, error=err_msg)
            emit({"type": "error", "content": err_msg})
            return ChatResult(emitted_events=list(session_events),last_text=last_text_buffer, success=False, next_event_number=next_event_number,
                              is_complete=is_complete, error=err_msg)

        finish_reason = None
        if last_chunk and last_chunk.candidates:
            try:
                finish_reason = last_chunk.candidates[0].finish_reason
            except Exception:
                pass

        finish_reason_str = str(finish_reason or "").upper()
        is_stop = "STOP" in finish_reason_str
        is_malformed = "MALFORMED" in finish_reason_str
        is_max_tokens = "MAX_TOKENS" in finish_reason_str

        # ── Tool execution ────────────────────────────────────────────────────
        if active_tool_calls:
            turn_retries = 0  # real progress → reset bad-turn counter

            if await _is_cancelled():
                return ChatResult(emitted_events=list(session_events),
                    success=False, next_event_number=next_event_number,
                    is_complete=is_complete, error="Cancelled before tool execution"
                )

            async def _execute(call_tuple):
                call_id, fc, validation_error, coerced_args = call_tuple
                if _is_event_tool(fc.name):
                    if validation_error is not None:
                        return call_id, fc, {
                            "error": (
                                "The payload did not match AddItineraryEvent schema. "
                                f"Fix and retry. Error: {validation_error}"
                            )
                        }
                    return call_id, fc, {
                        "status": "success",
                        "message": "Event added to timeline.",
                        "event_number": coerced_args.get("event_number"),
                    }

                _timeout = TIMEOUTS.get(fc.name, 60)
                _started = time.monotonic()
                try:
                    mcp_result = await session.call_tool(fc.name, dict(fc.args or {}))
                    output = (
                        "".join(c.text for c in mcp_result.content if hasattr(c, "text"))
                        or "Task completed."
                    )
                    _elapsed = time.monotonic() - _started
                    _raw_len = len(output)
                    _cap = _TOOL_RESPONSE_CAPS.get(fc.name, _DEFAULT_RESPONSE_CAP)
                    if _raw_len > _cap:
                        output = output[:_cap] + f"\n…[truncated, {_raw_len - _cap} chars dropped]"
                    log.info(
                        "Tool done",
                        node=node_name,
                        tool=fc.name,
                        elapsed_s=round(_elapsed, 2),
                        raw_chars=_raw_len,
                        sent_chars=len(output),
                    )
                    return call_id, fc, {"output": output}
                except asyncio.CancelledError:
                    log.info("Tool cancelled", node=node_name, tool=fc.name)
                    raise
                except Exception as e:
                    _elapsed = time.monotonic() - _started
                    log.error(
                        "Tool execution failed",
                        node=node_name,
                        tool=fc.name,
                        elapsed_s=round(_elapsed, 2),
                        error=str(e),
                    )
                    return call_id, fc, {"error": str(e)}

            _batch_started = time.monotonic()
            _mcp_calls = [t for t in active_tool_calls if not _is_event_tool(t[1].name)]
            try:
                gathered = await asyncio.gather(*(_execute(t) for t in active_tool_calls))
            except asyncio.CancelledError:
                raise
            _batch_elapsed = time.monotonic() - _batch_started
            if _mcp_calls:
                log.info(
                    "Tool batch done",
                    node=node_name,
                    turn=turn_count,
                    mcp_calls=len(_mcp_calls),
                    total_calls=len(active_tool_calls),
                    batch_s=round(_batch_elapsed, 2),
                    tools=[t[1].name for t in _mcp_calls],
                )

            tool_responses = []
            for call_id, fc, result in gathered:
                if not _is_event_tool(fc.name):
                    emit({
                        "type": "tool_response",
                        "tool_name": fc.name,
                        "response": result,
                        "call_id": call_id,
                    })
                tool_responses.append(
                    types.Part.from_function_response(name=fc.name, response=result)
                )

            current_message = tool_responses

            # ── Token-aware summarizing sliding window ────────────────────────
            try:
                current_history = list(chat.get_history())
                if await _needs_pruning(client, current_history, config=config):
                    log.info("Pruning history", node=node_name)
                    emit({
                        "type": "pruning",
                        "content": (
                            "Context window filling up — summarizing and "
                            "dropping older messages to free room."
                        ),
                    })
                    pruned, dropped, summary = await _prune_history(
                        client, current_history, config=config
                    )
                    if dropped > 0:
                        chat = client.aio.chats.create(
                            model=_MODEL, config=config, history=pruned
                        )
                        log.info(
                            "History pruned and chat rebuilt",
                            node=node_name,
                            dropped=dropped,
                            recap_injected=bool(summary),
                        )
            except Exception as prune_err:
                log.warning("History pruning failed", node=node_name, error=str(prune_err))

            # Research node: stop as soon as START event is emitted.
            if stop_after_start and start_emitted:
                return ChatResult(emitted_events=list(session_events),
                    success=True,
                    next_event_number=next_event_number,
                    is_complete=False,
                    last_text=last_text_buffer,
                )

            continue  # next turn

        # ── No tool calls this turn ───────────────────────────────────────────
        if is_complete:
            if not is_stop:
                log.info(
                    "Post-END turn with non-STOP finish_reason; treating as success",
                    node=node_name, finish_reason=finish_reason_str,
                )
            return ChatResult(emitted_events=list(session_events),
                success=True, next_event_number=next_event_number, is_complete=True
            )

        if is_stop:
            # Model stopped cleanly.
            # - research node (stop_after_start): success if START was emitted.
            # - day planner (require_end=False): clean STOP means the day is done;
            #   END is emitted later by the finalizer, not here.
            # - finalizer (require_end=True): missing END is a genuine error.
            if stop_after_start and start_emitted:
                return ChatResult(emitted_events=list(session_events),
                    success=True, next_event_number=next_event_number, is_complete=False,
                    last_text=last_text_buffer,
                )
            if not require_end:
                return ChatResult(emitted_events=list(session_events),
                    success=True, next_event_number=next_event_number, is_complete=False,
                    last_text=last_text_buffer,
                )
            emit({
                "type": "error",
                "content": (
                    f"Agent stopped cleanly but never emitted an END event "
                    f"(finish_reason={finish_reason}, node={node_name})."
                ),
            })
            log.error(f"Agent stopped cleanly but never emitted an END event", node=node_name, finish_reason=finish_reason)
            return ChatResult(emitted_events=list(session_events),
                success=False, next_event_number=next_event_number,
                is_complete=False, error="Clean stop without END"
            )

        if is_max_tokens:
            # Rebuild from history_snapshot (discarding the runaway turn) and
            # push the model to emit ONE concrete tool call immediately.
            if turn_retries >= max_turn_retries:
                err = (
                    f"MAX_TOKENS hit {turn_retries + 1} times in a row in node "
                    f"'{node_name}'; giving up."
                )
                emit({"type": "error", "content": err})
                log.error(f"MAX_TOKENS hit {turn_retries + 1} times in a row", node=node_name)
                return ChatResult(emitted_events=list(session_events),
                    success=False, next_event_number=next_event_number,
                    is_complete=False, error=err,
                )
            turn_retries += 1
            log.warning(
                "MAX_TOKENS — rebuilding and nudging toward a single tool call",
                node=node_name, retry=f"{turn_retries}/{max_turn_retries}",
            )
            emit({
                "type": "system",
                "content": (
                    "Model exceeded the output-token budget while thinking. "
                    f"Retrying ({turn_retries}/{max_turn_retries}) with a nudge "
                    "to emit the next event directly."
                ),
                "error": finish_reason_str,
            })
            try:
                chat = client.aio.chats.create(
                    model=_MODEL, config=config,
                    history=_baseline_history() or history_snapshot,
                )
                log.info(f"Rebuilt after MAX_TOKENS", node=node_name)
            except Exception as rebuild_err:
                err = f"Failed to rebuild after MAX_TOKENS: {rebuild_err}"
                emit({"type": "error", "content": err})
                log.error(f"Failed to rebuild after MAX_TOKENS", node=node_name, error=str(rebuild_err))
                return ChatResult(emitted_events=list(session_events),
                    success=False, next_event_number=next_event_number,
                    is_complete=False, error=err,
                )
            current_message = (
                "Your previous turn exceeded the output-token budget before "
                "emitting any tool call — so nothing was saved. "
                "STOP thinking out a full plan. Emit ONLY the single next "
                "concrete event as a well-formed tool call right now. "
                "Do not narrate, do not outline future events — just the one "
                "next event as a function call. Continue chronologically "
                "from the last emitted event; do not duplicate prior events."
            )
            continue

        if is_malformed:
            if turn_retries >= max_turn_retries:
                err = (
                    f"MALFORMED_FUNCTION_CALL {turn_retries + 1} times in a row "
                    f"in node '{node_name}'; giving up."
                )
                emit({"type": "error", "content": err})
                log.error(f"MALFORMED_FUNCTION_CALL {turn_retries + 1} times in a row", node=node_name)
                return ChatResult(emitted_events=list(session_events),
                    success=False, next_event_number=next_event_number,
                    is_complete=False, error=err
                )

            turn_retries += 1
            log.warning(
                "MALFORMED_FUNCTION_CALL — rebuilding and nudging",
                node=node_name, retry=f"{turn_retries}/{max_turn_retries}",
            )
            emit({
                "type": "system",
                "content": (
                    "Model turn ended without valid output. "
                    f"Retrying ({turn_retries}/{max_turn_retries})."
                ),
                "error": finish_reason_str,
            })
            try:
                chat = client.aio.chats.create(
                    model=_MODEL, config=config,
                    history=_baseline_history() or history_snapshot,
                )
                log.info(f"Rebuilt after MALFORMED", node=node_name)
            except Exception as rebuild_err:
                err = f"Failed to rebuild after MALFORMED: {rebuild_err}"
                emit({"type": "error", "content": err})
                log.error(f"Failed to rebuild after MALFORMED", node=node_name, error=str(rebuild_err))
                return ChatResult(emitted_events=list(session_events),
                    success=False, next_event_number=next_event_number,
                    is_complete=False, error=err
                )
            current_message = (
                "Your previous turn ended without emitting a valid next step "
                f"(finish_reason={finish_reason}). No events were saved. "
                "Please re-emit the EXACT next step as a well-formed tool call — "
                "every required argument must be present and JSON-valid. "
                "Continue from where you left off; do not skip or duplicate events."
            )
            continue

        # Any other non-STOP / non-MALFORMED reason without END.
        # For day planner (require_end=False) this is still a real failure —
        # MAX_TOKENS / SAFETY etc. mean the model couldn't continue cleanly.
        err = (
            f"Agent turn ended with finish_reason={finish_reason} "
            f"in node '{node_name}'; giving up."
        )
        emit({"type": "error", "content": err})
        log.error(f"Agent turn ended with finish_reason={finish_reason}", node=node_name)
        return ChatResult(emitted_events=list(session_events),
            success=False, next_event_number=next_event_number,
            is_complete=False, error=err
        )
