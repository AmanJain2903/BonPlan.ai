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

# Tools whose responses carry durable cross-day facts (policies, round-trip
# coverage, booking tokens) that emitted events don't capture. Responses
# from these tools get snapshotted and surfaced to the knowledge-extractor
# at the end of the day.
_KNOWLEDGE_TOOL_NAMES: set[str] = {
    "search_hotels",
    "search_flights",
    "search_multi_city_flights",
    "get_next_flights",
    "search_rental_cars",
    "get_place_info",
    "get_flight_booking_details",
    "get_hotel_booking_url",
}

_MODEL = settings.PLANNER_AGENT_MODEL
_PRUNING_MODEL = settings.CONTEXT_PRUNING_MODEL


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

# Token-based history pruning.  Trigger pruning when history approaches
# `_PRUNE_THRESHOLD_RATIO` of the model's context window; after pruning aim for
# `_PRUNE_TARGET_RATIO`.  The first history item (the initial user message) is
# always preserved — it contains the node-specific task prompt.
_PRUNE_THRESHOLD_RATIO = 0.25
_PRUNE_TARGET_RATIO = 0.15
_PRUNE_MAX_ITERS = 12

# Safety floor: even if token counting fails we never let history grow
# unbounded. This caps total items (2 per turn + the initial message).
_SAFETY_MAX_ITEMS = 30


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
    return total_chars // 4


async def _count_tokens_safe(client, history: list) -> Optional[int]:
    """Return total tokens; fall back to char/4 estimate if the SDK call fails."""
    if not history:
        return 0
    try:
        resp = await client.aio.models.count_tokens(model=_MODEL, contents=history)
        t = int(getattr(resp, "total_tokens", 0) or 0)
        if t > 0:
            return t
        log.info("count_tokens successful")
    except Exception as exc:
        log.debug("count_tokens failed; using char estimate", error=str(exc))
    return _estimate_tokens_from_chars(history)


def _render_history_for_summary(items: list) -> str:
    """Flatten a list of Content items into plain text for the summarizer."""
    lines: list[str] = []
    for item in items:
        role = getattr(item, "role", None) or "unknown"
        parts = getattr(item, "parts", None) or []
        chunks: list[str] = []
        for p in parts:
            txt = getattr(p, "text", None)
            if isinstance(txt, str) and txt.strip():
                chunks.append(txt.strip())
                continue
            fc = getattr(p, "function_call", None)
            if fc is not None:
                try:
                    args_preview = str(dict(fc.args or {}))[:400]
                except Exception:
                    args_preview = ""
                chunks.append(f"[tool_call {fc.name}] {args_preview}")
                continue
            fr = getattr(p, "function_response", None)
            if fr is not None:
                try:
                    resp_preview = str(getattr(fr, "response", ""))[:400]
                except Exception:
                    resp_preview = ""
                chunks.append(f"[tool_response {getattr(fr, 'name', '')}] {resp_preview}")
                continue
        if chunks:
            lines.append(f"{role}: " + " | ".join(chunks))
    return "\n".join(lines)


async def _summarize_dropped(dropped_items: list) -> str:
    """
    Ask the pruning model to compress the dropped turns into a dense recap.
    Falls back to a deterministic text stub if the pruning client is absent or
    the call fails — the calling code never raises.
    """
    pruning_client = runtime.pruning_client
    rendered = _render_history_for_summary(dropped_items)
    if not rendered:
        return "(older context elided)"

    fallback = (
        "[Older context compressed] "
        + rendered[:1200].replace("\n", " ")
    )

    if pruning_client is None:
        return fallback

    prompt = (
        "You are compressing earlier turns of an AI travel-planning conversation. "
        "Produce a tight recap (<=600 tokens) that preserves: tools already called "
        "and their key findings (hotels/flights/places/routes chosen or ruled out), "
        "coordinates/IDs referenced, user preferences the model has committed to, "
        "and any decisions already made. Drop chit-chat. Use bullet points. "
        "Do NOT fabricate details. Do NOT re-emit events. Do NOT include markdown headers.\n\n"
        "--- DROPPED TURNS START ---\n"
        f"{rendered}\n"
        "--- DROPPED TURNS END ---\n\n"
        "Recap:"
    )
    try:
        resp = await pruning_client.aio.models.generate_content(
            model=_PRUNING_MODEL,
            contents=prompt,
        )
        text = (getattr(resp, "text", None) or "").strip()
        if text:
            return "[Earlier-context recap]\n" + text
        log.info("Summarization pruning successful")
    except Exception as exc:
        log.debug("Summarization pruning failed; using fallback stub", error=str(exc))
    return fallback


async def _prune_history(client, history: list) -> tuple[list, int, str | None]:
    """
    Token-aware summarizing sliding window.

    Returns `(new_history, dropped_count, summary_text_or_None)`.

    - Always preserves history[0] (initial user message).
    - When total tokens exceed the threshold, drops oldest non-initial items
      (2 at a time) until under the target ratio, summarizes the dropped turns
      via the pruning client, and injects the summary as a synthetic user
      message at position 1 so the main model keeps continuity.
    - If token counting fails, falls back to a fixed-item cap.
    """
    if len(history) <= 1:
        return history, 0, None

    threshold = int(settings.PLANNER_AGENT_MODEL_CONTEXT_WINDOW * _PRUNE_THRESHOLD_RATIO)
    target = int(settings.PLANNER_AGENT_MODEL_CONTEXT_WINDOW * _PRUNE_TARGET_RATIO)

    total = await _count_tokens_safe(client, history)
    if total is None:
        # Token-counting unavailable → fall back to item cap without summarizing.
        if len(history) <= _SAFETY_MAX_ITEMS:
            return history, 0, None
        keep_tail = _SAFETY_MAX_ITEMS - 1
        dropped = history[1:-keep_tail]
        summary = await _summarize_dropped(dropped)
        pruned = history[:1] + [_summary_content(summary)] + history[-keep_tail:]
        return pruned, len(dropped), summary

    if total <= threshold:
        return history, 0, None

    pruned = list(history)
    dropped_acc: list = []
    for _ in range(_PRUNE_MAX_ITERS):
        if len(pruned) <= 3:
            break
        dropped_acc.extend(pruned[1:3])
        pruned = pruned[:1] + pruned[3:]
        current = await _count_tokens_safe(client, pruned)
        if current is None or current <= target:
            break

    if not dropped_acc:
        return history, 0, None

    summary = await _summarize_dropped(dropped_acc)
    # Insert the recap as a synthetic user message right after the initial
    # prompt so the main model treats it as authoritative context.
    pruned = pruned[:1] + [_summary_content(summary)] + pruned[1:]
    return pruned, len(dropped_acc), summary


def _summary_content(summary: str):
    """Wrap a recap string as a user-role Content so the chat history accepts it."""
    return types.Content(role="user", parts=[types.Part.from_text(text=summary)])


@dataclass
class ChatResult:
    success: bool
    next_event_number: int
    is_complete: bool          # True if END event was emitted
    error: Optional[str] = None
    last_text: Optional[str] = None  # last non-thought text chunk emitted by the model
    emitted_events: list = None  # events successfully emitted during this chat loop
    tool_findings: list = None   # compact (tool, args, response) for knowledge-tool calls


async def run_chat_loop(
    *,
    initial_message: Any,
    config: types.GenerateContentConfig,
    node_name: str,
    next_event_number: int,
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

    current_message: Any = initial_message
    is_complete = False
    start_emitted = False
    # Running list of events emitted within this chat loop. Combined with
    # `prior_events` (from persisted state) to feed the placement validator.
    session_events: list = []
    # Snapshots of hotel/flight/car search responses this session so the
    # end-of-day knowledge extractor can surface policies + round-trip
    # coverage for the next day's planner.
    session_tool_findings: list = []
    _all_prior_events = list(prior_events or [])
    last_text_buffer: str = ""
    pending_turn_text: str = ""

    max_turn_retries = 3
    turn_retries = 0
    max_turns = 45
    turn_count = 0

    while True:
        if await _is_cancelled():
            return ChatResult(tool_findings=list(session_tool_findings), emitted_events=list(session_events),last_text=last_text_buffer, success=False, next_event_number=next_event_number,
                              is_complete=is_complete, error="Cancelled")

        if turn_count >= max_turns:
            log.error("Node turn cap reached", node=node_name, turns=turn_count)
            emit({"type": "error", "content": f"Node '{node_name}' exceeded turn budget."})
            return ChatResult(tool_findings=list(session_tool_findings), emitted_events=list(session_events),last_text=last_text_buffer, success=False, next_event_number=next_event_number,
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
                response_stream = await chat.send_message_stream(current_message)

                async for chunk in response_stream:
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
                            if is_thought or not is_complete:
                                emit({"type": "thinking", "content": part.text})
                            else:
                                emit({"type": "summary", "content": part.text})
                            if not is_thought:
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

                                validation_error, coerced_args = validate_itinerary_event(
                                    args,
                                    mode=mode,
                                    is_resuming=is_resuming,
                                    prior_events=combined_prior,
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
                                    log.warning(
                                        "Invalid event tool call — asking agent to retry",
                                        node=node_name,
                                        tool=fc.name,
                                        validation_error=str(validation_error),
                                    )
                            else:
                                active_tool_calls.append((call_id, fc, None, None))
                                emit({
                                    "type": "tool_call",
                                    "tool_name": fc.name,
                                    "args": dict(fc.args or {}),
                                    "call_id": call_id,
                                })

                    if await _is_cancelled():
                        return ChatResult(tool_findings=list(session_tool_findings), emitted_events=list(session_events),
                            success=False, next_event_number=next_event_number,
                            is_complete=is_complete, error="Cancelled mid-stream"
                        )

                stream_ok = True
                if pending_turn_text.strip():
                    last_text_buffer = pending_turn_text
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
            return ChatResult(tool_findings=list(session_tool_findings), emitted_events=list(session_events),last_text=last_text_buffer, success=False, next_event_number=next_event_number,
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
                return ChatResult(tool_findings=list(session_tool_findings), emitted_events=list(session_events),
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
                try:
                    mcp_result = await asyncio.wait_for(
                        session.call_tool(fc.name, dict(fc.args or {})),
                        timeout=_timeout,
                    )
                    output = (
                        "".join(c.text for c in mcp_result.content if hasattr(c, "text"))
                        or "Task completed."
                    )
                    return call_id, fc, {"output": output}
                except asyncio.TimeoutError:
                    log.warning("Tool timeout", node=node_name, tool=fc.name, timeout=_timeout)
                    return call_id, fc, {
                        "error": f"Tool {fc.name} timed out after {_timeout}s."
                    }
                except asyncio.CancelledError:
                    log.info("Tool cancelled", node=node_name, tool=fc.name)
                    raise
                except Exception as e:
                    log.error("Tool execution failed", node=node_name, tool=fc.name, error=str(e))
                    return call_id, fc, {"error": str(e)}

            try:
                gathered = await asyncio.gather(*(_execute(t) for t in active_tool_calls))
            except asyncio.CancelledError:
                raise

            tool_responses = []
            for call_id, fc, result in gathered:
                if (
                    not _is_event_tool(fc.name)
                    and fc.name in _KNOWLEDGE_TOOL_NAMES
                    and isinstance(result, dict)
                    and "output" in result
                ):
                    try:
                        raw_args = dict(fc.args or {})
                    except Exception:
                        raw_args = {}
                    # Hard cap per finding so a chatty tool can't bloat state.
                    session_tool_findings.append({
                        "tool": fc.name,
                        "args": raw_args,
                        "response": str(result.get("output") or "")[:4000],
                    })
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
                pruned, dropped, summary = await _prune_history(client, current_history)
                if dropped > 0:
                    emit({
                        "type": "pruning",
                        "content": (
                            f"Compressing {dropped} older message(s) into a recap to "
                            "stay within the model's context window."
                        ),
                        "summary": summary,
                        "dropped": dropped,
                    })
                    chat = client.aio.chats.create(
                        model=_MODEL, config=config, history=pruned
                    )
                    log.info(
                        "History pruned",
                        node=node_name,
                        before=len(current_history),
                        after=len(pruned),
                        dropped=dropped,
                    )
            except Exception as prune_err:
                log.warning("History pruning failed", node=node_name, error=str(prune_err))

            # Research node: stop as soon as START event is emitted.
            if stop_after_start and start_emitted:
                return ChatResult(tool_findings=list(session_tool_findings), emitted_events=list(session_events),
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
            return ChatResult(tool_findings=list(session_tool_findings), emitted_events=list(session_events),
                success=True, next_event_number=next_event_number, is_complete=True
            )

        if is_stop:
            # Model stopped cleanly.
            # - research node (stop_after_start): success if START was emitted.
            # - day planner (require_end=False): clean STOP means the day is done;
            #   END is emitted later by the finalizer, not here.
            # - finalizer (require_end=True): missing END is a genuine error.
            if stop_after_start and start_emitted:
                log.info(f"Research node stopped", node=node_name)
                return ChatResult(tool_findings=list(session_tool_findings), emitted_events=list(session_events),
                    success=True, next_event_number=next_event_number, is_complete=False,
                    last_text=last_text_buffer,
                )
            if not require_end:
                log.info(f"Day planner stopped", node=node_name)
                return ChatResult(tool_findings=list(session_tool_findings), emitted_events=list(session_events),
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
            return ChatResult(tool_findings=list(session_tool_findings), emitted_events=list(session_events),
                success=False, next_event_number=next_event_number,
                is_complete=False, error="Clean stop without END"
            )

        if is_max_tokens:
            # Gemma blew the OUTPUT-token ceiling, almost always because it
            # was thinking out an entire day's plan before calling any tool.
            # Rebuild from history_snapshot (discarding the runaway turn) and
            # push the model to emit ONE concrete tool call immediately.
            if turn_retries >= max_turn_retries:
                err = (
                    f"MAX_TOKENS hit {turn_retries + 1} times in a row in node "
                    f"'{node_name}'; giving up."
                )
                emit({"type": "error", "content": err})
                log.error(f"MAX_TOKENS hit {turn_retries + 1} times in a row", node=node_name)
                return ChatResult(tool_findings=list(session_tool_findings), emitted_events=list(session_events),
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
            # Force pruning before rebuild — long histories compound the problem.
            try:
                pruned, dropped, summary = await _prune_history(client, history_snapshot)
                if dropped > 0:
                    emit({
                        "type": "pruning",
                        "content": f"Compressing {dropped} older message(s) after MAX_TOKENS.",
                        "summary": summary,
                        "dropped": dropped,
                    })
                    history_snapshot = pruned
            except Exception as prune_err:
                log.warning("Post-MAX_TOKENS pruning failed", node=node_name, error=str(prune_err))
            try:
                chat = client.aio.chats.create(
                    model=_MODEL, config=config,
                    history=history_snapshot,
                )
                log.info(f"Rebuilt after MAX_TOKENS", node=node_name)
            except Exception as rebuild_err:
                err = f"Failed to rebuild after MAX_TOKENS: {rebuild_err}"
                emit({"type": "error", "content": err})
                log.error(f"Failed to rebuild after MAX_TOKENS", node=node_name, error=str(rebuild_err))
                return ChatResult(tool_findings=list(session_tool_findings), emitted_events=list(session_events),
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
                return ChatResult(tool_findings=list(session_tool_findings), emitted_events=list(session_events),
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
                    history=history_snapshot,
                )
                log.info(f"Rebuilt after MALFORMED", node=node_name)
            except Exception as rebuild_err:
                err = f"Failed to rebuild after MALFORMED: {rebuild_err}"
                emit({"type": "error", "content": err})
                log.error(f"Failed to rebuild after MALFORMED", node=node_name, error=str(rebuild_err))
                return ChatResult(tool_findings=list(session_tool_findings), emitted_events=list(session_events),
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
        return ChatResult(tool_findings=list(session_tool_findings), emitted_events=list(session_events),
            success=False, next_event_number=next_event_number,
            is_complete=False, error=err
        )
