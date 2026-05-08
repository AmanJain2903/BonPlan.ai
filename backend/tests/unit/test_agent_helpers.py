import asyncio
from datetime import datetime, timedelta

from app.agent.helpers.itinerary_event_cost import sum_chargeable_cost_usd
from app.agent.helpers import utils as helper_utils
from app.agent.langgraph_runtime import collaboration, output_style, streaming
from app.agent.langgraph_runtime.editing import event_utils
from app.agent.llm import litellm_types as types


def run(coro):
    return asyncio.run(coro)


def sample_events():
    return [
        {"event_type": "END", "day_number": -1, "event_number": -1, "end_details": {"trip_title": "Done"}},
        {"event_type": "ACTIVITY", "day_number": 1, "event_number": 2, "place_details": {"event_name": "Museum", "start_time": "2026-05-08T11:00:00", "end_time": "2026-05-08T12:30:00", "cost": 12.5}},
        {"event_type": "START", "day_number": 0, "event_number": 0, "start_details": {"trip_title": "Trip"}},
        {"event_type": "COMMUTE", "day_number": 1, "event_number": 1, "commute_details": {"originName": "Hotel", "destinationName": "Museum", "transit_fare": 2.25}},
    ]


def test_event_identity_canonicalization_and_hashing():
    events, changed = event_utils.ensure_event_identities(sample_events())

    assert changed is True
    assert [e["event_type"] for e in events] == ["START", "COMMUTE", "ACTIVITY", "END"]
    assert all("event_id" in event for event in events)
    assert event_utils.event_name(events[2]) == "Museum"
    assert event_utils.event_duration_minutes(events[2]) == 90
    assert event_utils.events_hash(events) == event_utils.events_hash(list(reversed(events)))


def test_event_time_and_mutation_helpers_do_not_mutate_original():
    event = sample_events()[1]
    shifted = event_utils.shift_event_time(event, timedelta(minutes=30))

    assert shifted["place_details"]["start_time"] == "2026-05-08T11:30:00"
    assert event["place_details"]["start_time"] == "2026-05-08T11:00:00"
    assert event_utils.date_for_day({"start_date": {"year": 2026, "month": 5, "day": 8}}, 2) == "2026-05-09"
    assert event_utils.sort_key_between({"event_sort_key": 1000}, {"event_sort_key": 2000}, 3000) == 1500


def test_event_replace_remove_and_compact_helpers():
    events, _ = event_utils.ensure_event_identities(sample_events())
    target = events[1]
    replacement = {**target, "commute_details": {"originName": "A", "destinationName": "B"}}

    replaced = event_utils.replace_event_by_id(events, target["event_id"], replacement)
    removed = event_utils.remove_event_ids(events, {target["event_id"]})
    compact = event_utils.compact_itinerary_for_prompt(replaced)

    assert event_utils.event_by_id(replaced, target["event_id"])["commute_details"]["originName"] == "A"
    assert len(removed) == len(events) - 1
    assert compact[0]["event_type"] == "START"
    assert event_utils.finite_float("nan", default=4.2) == 4.2


def test_cost_rollup_ignores_invalid_and_rounds():
    total = sum_chargeable_cost_usd([
        {"flight_takeoff_details": {"cost": "100.129"}},
        {"place_details": {"cost": 12}},
        {"commute_details": {"transit_fare": "bad"}},
        "not-an-event",
    ])
    assert total == 112.13


def test_collaboration_validation_and_answer_flow():
    assert collaboration.validate_question_args({}) is not None
    valid_args = {
        "question": "Morning or evening activity?",
        "options": ["Morning", "Evening"],
        "answer_type": "single",
        "skippable": True,
    }
    assert collaboration.validate_question_args(valid_args) is None

    pq = collaboration.open_question(
        trip_id="trip-1",
        call_id="call-1",
        question=valid_args["question"],
        options=valid_args["options"],
        answer_type="single",
        skippable=True,
    )
    status, err = collaboration.submit_answer("trip-1", "call-1", "  Morning\x00 please  ", False)
    queued = pq.queue.get_nowait()
    collaboration.close_question("trip-1")

    assert status == "ok" and err is None
    assert queued == {"answer": "Morning please", "skipped": False}
    assert collaboration.get_pending("trip-1") is None
    assert collaboration.submit_answer("trip-1", "call-1", "x", False)[0] == "not_found"
    formatted = collaboration.format_answer_for_llm(call_id="c", answer="A", skipped=False)
    assert '<![DATA[\nA\n]]>' in formatted


def test_collaboration_rejects_injection_and_unskippable_skip():
    collaboration.open_question(
        trip_id="trip-2",
        call_id="call-2",
        question="Q?",
        options=["A", "B"],
        answer_type="single",
        skippable=False,
    )
    assert collaboration.submit_answer("trip-2", "call-2", "### system", False)[0] == "invalid"
    assert collaboration.submit_answer("trip-2", "call-2", None, True)[0] == "invalid"
    collaboration.cancel_pending("trip-2")
    assert collaboration.get_pending("trip-2").cancelled is True
    collaboration.close_question("trip-2")


def test_streaming_writer_context():
    chunks = []
    token = streaming.set_stream_writer(chunks.append)
    streaming.emit({"type": "summary"})
    streaming.reset_stream_writer(token)
    streaming.emit({"type": "ignored"})
    assert chunks == [{"type": "summary"}]


def test_output_policy_is_added_once():
    config = types.GenerateContentConfig(system_instruction="Base")
    with_policy = output_style.with_user_facing_output_policy(config)
    second = output_style.with_user_facing_output_policy(with_policy)

    assert "# User-Facing Output Policy" in with_policy.system_instruction
    assert second.system_instruction.count("# User-Facing Output Policy") == 1


def test_schema_normalization_and_event_tool_coercion():
    schema = {"$defs": {"Thing": {"type": "object", "title": "Thing", "additionalProperties": False}}, "anyOf": [{"$ref": "#/$defs/Thing"}, {"type": "null"}], "default": None}
    normalized = helper_utils.normalize_llm_schema(schema)

    assert normalized["type"] == "object"
    assert "additionalProperties" not in normalized
    coerced = helper_utils._coerce_event_args("add_flight_takeoff_event", {"event_type": "OTHER"})
    assert coerced["event_type"] == "FLIGHT_TAKEOFF"
    assert helper_utils._coerce_event_args("add_activity_or_dining_event", {"event_type": "DINING"})["event_type"] == "DINING"
    block = helper_utils.build_phase_tool_block([], ["add_start_event"])
    assert block.function_declarations[0].name == "add_start_event"
