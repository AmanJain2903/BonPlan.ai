# backend/app/agent/solo_planner.py

# Mock Agent Function
# import os
# import os
# import json
# from typing import AsyncGenerator, Dict, Any, Literal, Optional, Callable, Awaitable
# import asyncio

# relativePath = os.path.join(os.path.dirname(__file__), "mock_data")
# absolutePath = os.path.abspath(relativePath)
# mock_file_path = os.path.join(absolutePath, "mock_chunk_18_04_2026.json")
# baseDelay = 0.2 # in seconds

# delaysForChunks = {
#     "thinking": baseDelay,
#     "summary": baseDelay*1.1,
#     "tool_call": baseDelay*1.5,
#     "tool_response": baseDelay*2,
#     "event": baseDelay*2.5,
#     "system": baseDelay,
#     "error": baseDelay
# }

# async def generate_trip_itinerary(trip_payload: dict, mode: Literal["autonomous", "collaborative", "editing"] = "autonomous", current_trip_itinerary: Optional[list] = None, owner_id: Optional[str] = None, trip_id: Optional[str] = None, cancellation_callback: Optional[Callable[[], Awaitable[bool]]] = None) -> AsyncGenerator[Dict[str, Any], None]:

#     async def check_cancellation():
#         if cancellation_callback and await cancellation_callback():
#             return True
#         return False
    
#     if await check_cancellation():
#         return

#     with open(mock_file_path, "r") as f:
#         mock_chunks = json.load(f)
    
#     last_chunk = mock_chunks[-1]    
#     for chunk in mock_chunks[:-1]:
#         await asyncio.sleep(delaysForChunks[chunk["type"]])
#         yield chunk
#     await asyncio.sleep(5)
#     yield last_chunk

from typing import AsyncGenerator, Dict, Any, Literal, Optional, Callable, Awaitable
import asyncio
import json
import os
import uuid
from typing import AsyncGenerator, Any, Awaitable, Callable, Dict, Literal, Optional

from google.genai import types

from app.agent.core.runtime import runtime
from app.agent.schemas.structuredInput import TripInput
from app.agent.schemas.structuredOutput import AddItineraryEvent
from app.core.config import settings


AUTONOMOUS_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "autonomousPlannerPrompt.md")
with open(AUTONOMOUS_PROMPT_PATH, "r", encoding="utf-8") as f:
    AUTONOMOUS_PROMPT = f.read()

# COLLABORATIVE_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "collaborativePlannerPrompt.md")
# with open(COLLABORATIVE_PROMPT_PATH, "r", encoding="utf-8") as f:
#     COLLABORATIVE_PROMPT = f.read()

# EDITING_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "editingPlannerPrompt.md")
# with open(EDITING_PROMPT_PATH, "r", encoding="utf-8") as f:
#     EDITING_PROMPT = f.read()

planner_model = settings.PLANNER_AGENT_MODEL


# event_type -> the single `*_details` field that MUST be populated. Derived
# from AddItineraryEvent in app/agent/schemas/structuredOutput.py — every
# event type there maps 1-to-1 to a details field (ACTIVITY and DINING both
# share place_details).
_EVENT_TYPE_TO_DETAIL_FIELD = {
    "START": "start_details",
    "FLIGHT_TAKEOFF": "flight_takeoff_details",
    "FLIGHT_LAND": "flight_land_details",
    "HOTEL_CHECKIN": "hotel_checkin_details",
    "HOTEL_CHECKOUT": "hotel_checkout_details",
    "CAR_PICKUP": "car_pickup_details",
    "CAR_DROPOFF": "car_dropoff_details",
    "DINING": "place_details",
    "ACTIVITY": "place_details",
    "COMMUTE": "commute_details",
    "OTHER": "other_details",
    "END": "end_details",
}
_ALL_DETAIL_FIELDS = set(_EVENT_TYPE_TO_DETAIL_FIELD.values())
_ALLOWED_TOP_LEVEL = {
    "day_number",
    "day_title",
    "date",
    "event_number",
    "event_type",
} | _ALL_DETAIL_FIELDS


def _validate_itinerary_event(args: dict) -> tuple[Optional[str], Optional[dict]]:
    """Strict, event_type-aware validation for add_itinerary_event payloads.

    Returns ``(error_message, coerced_args)``. On success ``coerced_args`` is
    the pydantic-normalized dict (so ``"15.00"`` becomes ``15.0``, ``"3"``
    becomes ``3``, etc.) and ``error_message`` is ``None``. On failure the
    coerced dict is ``None`` and the error message is a human-readable string
    safe to feed back to the agent as a tool-response so it can self-correct.
    """
    if not isinstance(args, dict):
        return "Arguments must be a JSON object.", None

    # 1. event_type required + known
    event_type = args.get("event_type")
    if not event_type:
        return "Missing required field 'event_type'.", None
    if event_type not in _EVENT_TYPE_TO_DETAIL_FIELD:
        return (
            f"Invalid event_type '{event_type}'. Must be one of "
            f"{sorted(_EVENT_TYPE_TO_DETAIL_FIELD)}."
        ), None

    # 2. no unknown top-level keys
    extras = [k for k in args if k not in _ALLOWED_TOP_LEVEL]
    if extras:
        return (
            f"Unknown/extra top-level fields not allowed: {extras}. "
            f"Allowed fields: {sorted(_ALLOWED_TOP_LEVEL)}."
        ), None

    # 3. the correct details field for this event_type must be populated
    expected = _EVENT_TYPE_TO_DETAIL_FIELD[event_type]
    if args.get(expected) in (None, {}, []):
        return (
            f"event_type={event_type} requires '{expected}' to be populated."
        ), None

    # 4. every OTHER details field must be null/absent
    wrong = [
        f
        for f in _ALL_DETAIL_FIELDS
        if f != expected and args.get(f) is not None
    ]
    if wrong:
        return (
            f"event_type={event_type} must ONLY populate '{expected}'. "
            f"Remove these incorrectly populated fields: {wrong}."
        ), None

    # 5. full schema validation (also performs type coercion: "15.00" -> 15.0,
    #    "3" -> 3, etc.). We return the coerced dict so callers use the
    #    normalized values downstream (DB, SSE stream, frontend).
    try:
        validated = AddItineraryEvent(**args)
    except Exception as e:
        return f"Schema validation failed: {e}", None

    return None, validated.model_dump(exclude_none=True)


async def generate_trip_itinerary(
    trip_payload: dict,
    current_trip_itinerary: Optional[list] = None,
    mode: Literal["autonomous", "collaborative", "editing"] = "autonomous",
    owner_id: Optional[str] = None,
    trip_id: Optional[str] = None,
    cancellation_callback: Optional[Callable[[], Awaitable[bool]]] = None,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Stream itinerary-building chunks for a trip.

    On cancellation or any terminal error the generator prints a short
    status line and returns cleanly. Callers should treat the appearance
    of a ``{"type": "error", ...}`` chunk as terminal — no further chunks
    will follow.
    """

    async def is_cancelled() -> bool:
        if cancellation_callback is None:
            return False
        try:
            if await cancellation_callback():
                print(
                    f"[SOLO_PLANNER] Cancellation requested — stopping stream (trip_id={trip_id}).",
                    flush=True,
                )
                return True
        except Exception as e:
            # A broken callback must not kill the stream.
            print(f"[SOLO_PLANNER] Cancellation callback raised: {e}", flush=True)
        return False

    print(
        f"[SOLO_PLANNER] Starting generation (trip_id={trip_id}, mode={mode}).",
        flush=True,
    )

    try:
        if not runtime.is_ready:
            yield {
                "type": "system",
                "content": "Agent runtime initializing...",
                "error": "Agent runtime is not initialized yet. Please wait for the app to finish initializing."
            }
            return

        if mode != "autonomous":
            yield {
                "type": "system",
                "content": f"Mode '{mode}' not wired yet.",
                "error": "Mode not supported. Only 'autonomous' is supported."
            }
            return

        try:
            trip_data = TripInput(**trip_payload)
        except Exception as e:
            yield {"type": "error", "content": f"Invalid input: {e}"}
            return

        client = runtime.genai_client
        session = runtime.mcp_session
        planner_tool_block = runtime.planner_tool_block

        config = types.GenerateContentConfig(
            tools=[planner_tool_block],
            system_instruction=AUTONOMOUS_PROMPT,
            temperature=0.4, # Low temperature for deterministic output for maintaining JSON structure and creative enough for itinerary generation
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        chat = client.aio.chats.create(model=planner_model, config=config)

        current_message: Any = f"User Request:\n {trip_data.model_dump_json()}"
        if current_trip_itinerary:
            trip_itinerary_data = []
            for event in current_trip_itinerary:
                try:
                    eventData = AddItineraryEvent(**event)
                    trip_itinerary_data.append(eventData.model_dump())
                except Exception as e:
                    print(
                        f"[SOLO_PLANNER] Skipping malformed prior event: {e}",
                        flush=True,
                    )
                    continue
            if trip_itinerary_data:
                current_message += (
                    f"\n\nCurrent Trip Itinerary:\n {json.dumps(trip_itinerary_data, indent=2)}"
                )

        is_complete = False

        # Consecutive "turn ended bad" recoveries. Applies when the model
        # produced no tool calls AND did not emit END AND the finish_reason
        # is not STOP (e.g. MALFORMED_FUNCTION_CALL, MAX_TOKENS, OTHER, etc.).
        # We rebuild the chat from the pre-send snapshot and nudge the model
        # to retry the same step. The counter resets on any turn that makes
        # real progress (tool calls executed), so only *consecutive* bad
        # terminations count toward the cap.
        max_turn_retries = 3
        turn_retries = 0

        while True:
            if await is_cancelled():
                return

            max_retries = 6
            retry_delay = 2
            retry_exhausted_error: Optional[str] = None

            # Snapshot chat history so a mid-stream failure can be retried
            # against a fresh chat without the partial/corrupted turn.
            try:
                history_snapshot = list(chat.get_history())
            except Exception:
                history_snapshot = []

            active_tool_calls: list = []
            turn_text = ""
            last_chunk = None
            stream_ok = False

            for attempt in range(max_retries):
                active_tool_calls = []
                turn_text = ""
                last_chunk = None

                try:
                    response_stream = await chat.send_message_stream(current_message)

                    async for chunk in response_stream:
                        last_chunk = chunk

                        # Iterate parts directly instead of using the
                        # chunk.text aggregator. chunk.text silently skips any
                        # part with `thought=True`, so thinking traces from
                        # reasoning-capable models would never reach the UI.
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
                            # Text part — may be a thought trace or regular text.
                            if isinstance(part.text, str) and part.text:
                                turn_text += part.text
                                is_thought = bool(getattr(part, "thought", False))
                                # Thought-tagged reasoning always streams as
                                # "thinking". Regular text is "thinking" pre-END
                                # and "summary" post-END.
                                if is_thought or not is_complete:
                                    yield {"type": "thinking", "content": part.text}
                                else:
                                    yield {"type": "summary", "content": part.text}
                                continue

                            # Function call part.
                            if part.function_call:
                                fc = part.function_call
                                call_id = str(uuid.uuid4())

                                if fc.name == "add_itinerary_event":
                                    args = fc.args or {}
                                    # Event-type-aware validation so malformed
                                    # events never reach the DB. On failure,
                                    # don't yield the event; feed the error
                                    # back to the model via the tool-response
                                    # in this turn's gather. coerced_args is
                                    # the pydantic-normalized payload — use it
                                    # so coercions like "15.00" -> 15.0 reach
                                    # the UI and DB.
                                    validation_error, coerced_args = (
                                        _validate_itinerary_event(args)
                                    )

                                    active_tool_calls.append(
                                        (call_id, fc, validation_error)
                                    )

                                    if validation_error is None:
                                        if coerced_args.get("event_type") == "END":
                                            is_complete = True
                                        yield {
                                            "type": "event",
                                            "data": coerced_args,
                                            "call_id": call_id,
                                        }
                                    else:
                                        print(
                                            f"[SOLO_PLANNER] Invalid add_itinerary_event from agent — asking it to retry. Error: {validation_error}",
                                            flush=True,
                                        )
                                else:
                                    active_tool_calls.append((call_id, fc, None))
                                    yield {
                                        "type": "tool_call",
                                        "tool_name": fc.name,
                                        "args": fc.args,
                                        "call_id": call_id,
                                    }

                        if await is_cancelled():
                            return

                    stream_ok = True
                    break  # Success, exit retry loop

                except asyncio.CancelledError:
                    print(
                        f"[SOLO_PLANNER] Stream cancelled mid-flight (trip_id={trip_id}).",
                        flush=True,
                    )
                    raise

                except Exception as e:
                    err_str = str(e)
                    is_retryable = ("503" in err_str) or ("429" in err_str) or ("500" in err_str)

                    if is_retryable and attempt < max_retries - 1:
                        yield {
                            "type": "system",
                            "content": f"Transient upstream error. Retrying in {retry_delay}s... (Attempt {attempt + 1}/{max_retries})",
                            "error": err_str,
                        }
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2

                        # Rebuild chat from the pre-send snapshot so the
                        # retry doesn't see a half-written turn.
                        try:
                            chat = client.aio.chats.create(
                                model=planner_model,
                                config=config,
                                history=history_snapshot,
                            )
                        except Exception as rebuild_err:
                            retry_exhausted_error = (
                                f"Failed to rebuild chat for retry: {rebuild_err}"
                            )
                            break
                        continue

                    # Non-retryable or retries exhausted.
                    retry_exhausted_error = err_str
                    break

            if not stream_ok:
                err_msg = retry_exhausted_error or "Unknown streaming error."
                print(f"[SOLO_PLANNER] Terminal error: {err_msg}", flush=True)
                yield {"type": "error", "content": err_msg}
                return

            finish_reason = None
            if last_chunk and last_chunk.candidates:
                try:
                    finish_reason = last_chunk.candidates[0].finish_reason
                except Exception:
                    finish_reason = None

            # Termination decision:
            #   Rule A — is_complete=True with finish_reason == STOP: success.
            #   Rule B — is_complete=False AND finish_reason != STOP:
            #             transient model failure (MALFORMED_FUNCTION_CALL,
            #             MAX_TOKENS, OTHER, etc.). Rebuild chat from the
            #             pre-send snapshot and nudge the model to retry the
            #             same step. Cap at max_turn_retries consecutive
            #             attempts to avoid infinite loops.
            #   Rule C — is_complete=False AND finish_reason == STOP AND no
            #             active tool calls: model stopped cleanly without
            #             ever emitting END. Unrecoverable; error out.

            finish_reason_str = str(finish_reason or "").upper()
            is_stop = "STOP" in finish_reason_str
            is_malformed = "MALFORMED" in finish_reason_str

            if not active_tool_calls:
                # END already emitted — any termination here is terminal for
                # the planner. finish_reason == STOP is the happy path;
                # MAX_TOKENS / OTHER / SAFETY while streaming the final summary
                # is a benign cutoff (we already have a valid itinerary) and
                # must not retry (empty current_message would loop forever).
                if is_complete:
                    if not is_stop:
                        print(
                            f"[SOLO_PLANNER] Post-END turn ended with "
                            f"finish_reason={finish_reason}; treating as success.",
                            flush=True,
                        )
                    return

                # From here: END was never emitted.

                if is_stop:
                    # Rule C — clean stop without END, unrecoverable.
                    yield {
                        "type": "error",
                        "content": (
                            f"Agent stopped cleanly but never emitted an END "
                            f"event (finish_reason={finish_reason})."
                        ),
                    }
                    return

                if is_malformed:
                    # Rule B — retry path, capped.
                    if turn_retries >= max_turn_retries:
                        yield {
                            "type": "error",
                            "content": (
                                f"Agent turn ended with finish_reason={finish_reason} "
                                f"{turn_retries + 1} times in a row without emitting END; "
                                "giving up."
                            ),
                        }
                        return

                    turn_retries += 1
                    print(
                        f"[SOLO_PLANNER] Bad turn termination (finish_reason={finish_reason}) — "
                        f"rebuilding chat and nudging retry "
                        f"({turn_retries}/{max_turn_retries}).",
                        flush=True,
                    )
                    yield {
                        "type": "system",
                        "content": (
                            "Model turn ended without progress. "
                            f"Retrying the step ({turn_retries}/{max_turn_retries})."
                        ),
                        "error": finish_reason_str,
                    }
                    try:
                        chat = client.aio.chats.create(
                            model=planner_model,
                            config=config,
                            history=history_snapshot,
                        )
                    except Exception as rebuild_err:
                        yield {
                            "type": "error",
                            "content": (
                                f"Failed to rebuild chat after bad turn termination: "
                                f"{rebuild_err}"
                            ),
                        }
                        return
                    current_message = (
                        "Your previous turn ended without emitting a valid next step "
                        f"(finish_reason={finish_reason}). No events were saved for it. "
                        "Please re-emit the EXACT next step of the itinerary as a "
                        "well-formed tool call — ensure every required argument is "
                        "present and JSON is valid. Continue from where you left off; "
                        "do not skip or duplicate prior events."
                    )
                    continue

                # Any other non-STOP / non-MALFORMED reason without END
                # (MAX_TOKENS mid-plan, OTHER, SAFETY, RECITATION, etc.) —
                # error out; retrying here has historically not helped.
                yield {
                    "type": "error",
                    "content": (
                        f"Agent turn ended with finish_reason={finish_reason} "
                        "without emitting END; giving up."
                    ),
                }
                return

            # Turn produced at least one tool call — real progress. Reset the
            # consecutive-bad-turn counter so only runs of pure failures count
            # toward the cap.
            turn_retries = 0

            if await is_cancelled():
                return

            async def execute_tool(call_tuple):
                call_id, fc, validation_error = call_tuple
                if fc.name == "add_itinerary_event":
                    if validation_error is not None:
                        return call_id, fc, {
                            "error": (
                                "The payload you passed to add_itinerary_event did "
                                "not match the AddItineraryEvent schema and was "
                                "rejected before being saved. Fix the payload and "
                                "call add_itinerary_event again with the correct "
                                f"shape. Validation error: {validation_error}"
                            )
                        }
                            
                    result = {"status": "success", "message": "Event successfully added to the timeline!"}
                    return call_id, fc, result

                # Remote Tool Execution via MCP
                try:
                    mcp_result = await asyncio.wait_for(session.call_tool(fc.name, fc.args), timeout=60)
                    output = "".join(
                        [c.text for c in mcp_result.content if hasattr(c, "text")]
                    ) or "Task completed."
                    result = {"output": output}
                except asyncio.TimeoutError:
                    print(f"[SOLO_PLANNER] Timeout executing tool: {fc.name}", flush=True)
                    result = {"error": f"Tool {fc.name} timed out after 60 seconds."}
                except asyncio.CancelledError:
                    print(
                        f"[SOLO_PLANNER] Aborting in-flight tool: {fc.name}",
                        flush=True,
                    )
                    raise
                except Exception as e:
                    result = {"error": str(e)}
                return call_id, fc, result

            try:
                gathered_results = await asyncio.gather(
                    *(execute_tool(t) for t in active_tool_calls)
                )
            except asyncio.CancelledError:
                raise

            tool_responses = []
            for call_id, fc, result in gathered_results:
                if fc.name != "add_itinerary_event":
                    yield {
                        "type": "tool_response",
                        "tool_name": fc.name,
                        "response": result,
                        "call_id": call_id,
                    }
                tool_responses.append(
                    types.Part.from_function_response(name=fc.name, response=result)
                )

            current_message = tool_responses

    except asyncio.CancelledError:
        print(
            f"[SOLO_PLANNER] Generator cancelled (trip_id={trip_id}).",
            flush=True,
        )
        raise
    except Exception as e:
        import traceback

        traceback.print_exc()
        try:
            yield {"type": "error", "content": f"Runtime Error: {e}"}
        except Exception:
            pass
