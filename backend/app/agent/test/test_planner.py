"""
End-to-end planner smoke test.

Picks a random Trip from the DB, streams `generate_trip_itinerary` under a
real `agent_runtime_context` (MCP + GenAI), and records structured timing
metrics per run / per day / per event.

Output layout:
  app/agent/test/results/<DD-MM-YYYY_HH-MM-SS>/
    results.json               ← aggregate TestResults (progressive writes)
    chunks/
      chunk_<run_number>.json  ← the raw chunk stream for each run
"""
import asyncio
import json
import os
import random
import time
from datetime import datetime
from statistics import median
from typing import Dict, List, Optional

from pydantic import BaseModel
from sqlalchemy import select

from app.agent.core.runtime import agent_runtime_context
from app.agent.solo_planner import generate_trip_itinerary
from app.database.database import Session
from app.database.models.tripMembersTable import TripMember
from app.database.models.tripsTable import Trip

from app.core.config import settings

import sys

testResultsFolder = os.path.join(os.path.dirname(__file__), "results", "planner")
os.makedirs(testResultsFolder, exist_ok=True)

if len(sys.argv) > 1:
    RUNS = int(sys.argv[1])
else:
    print("No runs specified, using default of 1")
    RUNS = 1

def format_duration(seconds: Optional[float]) -> Optional[str]:
    if seconds is None:
        return None
    total = int(max(0, seconds))
    m, s = divmod(total, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_timestamp(epoch: float) -> str:
    """File-safe timestamp with day/month/year and H:M:S."""
    return time.strftime("%d-%m-%Y_%H:%M:%S", time.localtime(epoch))


class EventResults(BaseModel):
    event_number: int
    event_type: Optional[str] = None
    generated_at: Optional[str] = None
    time_from_last_event: Optional[str] = None
    time_from_day_start: Optional[str] = None


class DayResults(BaseModel):
    day_number: int
    first_event_time: Optional[str] = None
    last_event_time: Optional[str] = None
    day_run_time: Optional[str] = None
    event_count: int = 0
    tool_call_count: int = 0
    pruning_count: int = 0
    average_event_time: Optional[str] = None
    fastest_event_time: Optional[str] = None
    slowest_event_time: Optional[str] = None
    median_event_time: Optional[str] = None
    event_results: Dict[int, EventResults] = {}


class ChunkCounts(BaseModel):
    thinking: int = 0
    summary: int = 0
    tool_call: int = 0
    tool_response: int = 0
    event: int = 0
    pruning: int = 0
    system: int = 0
    error: int = 0
    unknown: int = 0
    total: int = 0


class RunResults(BaseModel):
    run_number: int
    trip_id: Optional[str] = None
    days: int = 0
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    run_time: Optional[str] = None
    average_day_time: Optional[str] = None
    fastest_day_time: Optional[str] = None
    slowest_day_time: Optional[str] = None
    median_day_time: Optional[str] = None
    time_to_first_token: Optional[str] = None
    time_to_start_event: Optional[str] = None
    time_to_end_event: Optional[str] = None
    time_to_first_day_event: Optional[str] = None
    time_to_finalize: Optional[str] = None
    total_events: int = 0
    total_day_events: int = 0
    total_tool_calls: int = 0
    total_pruning_events: int = 0
    total_pruning_drops: int = 0
    total_errors: int = 0
    total_system_messages: int = 0
    average_event_gap: Optional[str] = None
    fastest_event_gap: Optional[str] = None
    slowest_event_gap: Optional[str] = None
    median_event_gap: Optional[str] = None
    average_events_per_day: Optional[float] = None
    tool_usage: Dict[str, int] = {}
    chunk_counts: ChunkCounts = ChunkCounts()
    time_to_days_map: Dict[int, DayResults] = {}
    failed: bool = False
    error: Optional[str] = None


class TestResults(BaseModel):
    planner_agent_model: str = settings.PLANNER_AGENT_MODEL
    context_pruning_model: str = settings.CONTEXT_PRUNING_MODEL
    serper_content_parser_model: str = settings.SERPER_CONTENT_PARSER_MODEL
    num_runs: int = RUNS
    successful_runs: int = 0
    failed_runs: int = 0
    success_rate: Optional[float] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    test_time: Optional[str] = None
    average_time: Optional[str] = None
    fastest_time: Optional[str] = None
    slowest_time: Optional[str] = None
    median_time: Optional[str] = None
    total_events_all_runs: int = 0
    total_tool_calls_all_runs: int = 0
    total_pruning_events_all_runs: int = 0
    total_pruning_drops_all_runs: int = 0
    total_errors_all_runs: int = 0
    average_days_per_trip: Optional[float] = None
    average_events_per_day_all_runs: Optional[float] = None
    average_tool_calls_per_run: Optional[float] = None
    aggregate_tool_usage: Dict[str, int] = {}
    run_results: Dict[int, RunResults] = {}


async def get_trips():
    async with Session() as db:
        trips = (await db.execute(select(Trip))).scalars().all()
        return [trip.id for trip in trips]


async def get_trip_payload(trip_id: str):
    async with Session() as db:
        trip = (await db.execute(select(Trip).where(Trip.id == trip_id))).scalar_one_or_none()
        tripMembers = (
            await db.execute(select(TripMember).where(TripMember.trip_id == trip_id))
        ).scalars().first()
    if not trip:
        return None
    return {
        "hasMultipleDestinations": len(trip.destinations) > 1,
        "planning_type": trip.planning_type,
        "routing_style": trip.routing_style,
        "origin": trip.origin,
        "destinations": trip.destinations,
        "start_date": trip.start_date,
        "end_date": trip.end_date,
        "pace": trip.pace,
        "budget": trip.budget,
        "adults": trip.adults,
        "children": trip.children,
        "preferences": tripMembers.trip_preferences if tripMembers else {},
    }


def _write_results(results_file: str, testResults: TestResults) -> None:
    with open(results_file, "w") as f:
        json.dump(testResults.model_dump(mode="json"), f, indent=2)


def _write_chunks(chunk_file: str, chunks: list) -> None:
    with open(chunk_file, "w") as f:
        json.dump(chunks, f, indent=2)


async def run_test():
    print(f"------- Testing the BonPlan.ai Planner Agent for {RUNS} runs -------")
    timestamp = format_timestamp(time.time())
    test_results_folder = os.path.join(testResultsFolder, timestamp)
    os.makedirs(test_results_folder, exist_ok=True)

    chunks_folder = os.path.join(test_results_folder, "chunks")
    os.makedirs(chunks_folder, exist_ok=True)

    results_file = os.path.join(test_results_folder, "results.json")

    trip_ids = await get_trips()
    if not trip_ids:
        print("No trips found in the database.")
        return

    print(f"------------------- Test started at {timestamp} -------------------")
    print(f"------- Test results will be saved to {test_results_folder} -------")
    print("--------------------------------------------------------------------")

    testResults = TestResults()
    testStartTime = time.time()
    testResults.start_time = time.strftime("%H:%M:%S", time.localtime(testStartTime))
    run_times: list[float] = []

    # One shared runtime context across all runs — avoids repeatedly
    # spinning up the MCP subprocess and GenAI client.
    async with agent_runtime_context():
        for i in range(RUNS):
            run_number = i + 1
            print(f"\n=== Starting Run {run_number}/{RUNS} ===")
            trip_id = random.choice(trip_ids)
            test_trip_payload = await get_trip_payload(trip_id)

            runStartTime = time.time()
            runResults = RunResults(run_number=run_number, trip_id=str(trip_id))
            runResults.start_time = time.strftime("%H:%M:%S", time.localtime(runStartTime))

            last_event_time_epoch: float = runStartTime
            day_start_time_epoch: Dict[int, float] = {}
            chunks: list = []
            chunk_file = os.path.join(chunks_folder, f"chunk_{run_number}.json")
            event_gaps: List[float] = []
            day_event_gaps: Dict[int, List[float]] = {}
            current_day: int = 0
            last_day_event_time_epoch: Optional[float] = None

            try:
                async for chunk in generate_trip_itinerary(
                    test_trip_payload,
                    mode="autonomous",
                    user_id="test_user",
                    trip_id=str(trip_id),
                ):
                    chunks.append(chunk)
                    _write_chunks(chunk_file, chunks)

                    chunk_type = chunk.get("type", "unknown")
                    current_time_epoch = time.time()
                    runResults.chunk_counts.total += 1

                    # Every non-unknown chunk counts toward "first token".
                    if runResults.time_to_first_token is None and chunk_type != "unknown":
                        runResults.time_to_first_token = format_duration(
                            current_time_epoch - runStartTime
                        )

                    if chunk_type == "thinking":
                        runResults.chunk_counts.thinking += 1
                        print(f"{chunk.get('content', '')}", end="", flush=True)

                    elif chunk_type == "summary":
                        runResults.chunk_counts.summary += 1
                        print(f"{chunk.get('content', '')}")

                    elif chunk_type == "tool_call":
                        runResults.chunk_counts.tool_call += 1
                        runResults.total_tool_calls += 1
                        tool_name = chunk.get("tool_name") or "unknown"
                        runResults.tool_usage[tool_name] = (
                            runResults.tool_usage.get(tool_name, 0) + 1
                        )
                        if current_day > 0 and current_day in runResults.time_to_days_map:
                            runResults.time_to_days_map[current_day].tool_call_count += 1
                        args_str = json.dumps(chunk.get("args", {}))
                        print(f"\n[TOOL CALL] {tool_name} | Args: {args_str}")

                    elif chunk_type == "tool_response":
                        runResults.chunk_counts.tool_response += 1
                        resp_preview = json.dumps(chunk.get("response"), indent=2)[:500]
                        print(
                            f"[TOOL RESPONSE] {chunk.get('tool_name')} returned: "
                            f"{resp_preview} ... [truncated]"
                        )

                    elif chunk_type == "pruning":
                        runResults.chunk_counts.pruning += 1
                        runResults.total_pruning_events += 1
                        dropped = chunk.get("dropped") or 0
                        try:
                            runResults.total_pruning_drops += int(dropped)
                        except (TypeError, ValueError):
                            pass
                        if current_day > 0 and current_day in runResults.time_to_days_map:
                            runResults.time_to_days_map[current_day].pruning_count += 1
                        print(
                            f"\n[PRUNING] {chunk.get('content')} | dropped={dropped}"
                        )

                    elif chunk_type == "event":
                        runResults.chunk_counts.event += 1
                        runResults.total_events += 1
                        event_data = chunk.get("data", {}) or {}
                        et = event_data.get("event_type")

                        if et == "START":
                            runResults.time_to_start_event = format_duration(
                                current_time_epoch - runStartTime
                            )
                        elif et == "END":
                            runResults.time_to_end_event = format_duration(
                                current_time_epoch - runStartTime
                            )
                            if last_day_event_time_epoch is not None:
                                runResults.time_to_finalize = format_duration(
                                    current_time_epoch - last_day_event_time_epoch
                                )
                        else:
                            day_num = event_data.get("day_number")
                            evt_num = event_data.get("event_number")

                            if isinstance(day_num, int) and day_num > 0:
                                runResults.days = max(runResults.days, day_num)
                                runResults.total_day_events += 1
                                if day_num not in runResults.time_to_days_map:
                                    runResults.time_to_days_map[day_num] = DayResults(
                                        day_number=day_num,
                                    )
                                    runResults.time_to_days_map[day_num].first_event_time = (
                                        current_time_epoch
                                    )
                                    day_start_time_epoch[day_num] = current_time_epoch
                                    day_event_gaps[day_num] = []
                                    if runResults.time_to_first_day_event is None:
                                        runResults.time_to_first_day_event = format_duration(
                                            current_time_epoch - runStartTime
                                        )
                                current_day = day_num

                                day_res = runResults.time_to_days_map[day_num]
                                day_res.last_event_time = current_time_epoch
                                day_res.event_count += 1
                                last_day_event_time_epoch = current_time_epoch

                                gap = max(0.0, current_time_epoch - last_event_time_epoch)
                                event_gaps.append(gap)
                                day_event_gaps.setdefault(day_num, []).append(gap)

                                if isinstance(evt_num, int):
                                    evt_res = EventResults(
                                        event_number=evt_num,
                                        event_type=et,
                                        generated_at=time.strftime(
                                            "%H:%M:%S",
                                            time.localtime(current_time_epoch),
                                        ),
                                        time_from_last_event=format_duration(gap),
                                        time_from_day_start=format_duration(
                                            current_time_epoch
                                            - day_start_time_epoch.get(
                                                day_num, current_time_epoch
                                            )
                                        ),
                                    )
                                    day_res.event_results[evt_num] = evt_res
                                    last_event_time_epoch = current_time_epoch

                        print("\n=============================================")
                        print("[NEW ITINERARY EVENT EMITTED]")
                        print(json.dumps(event_data, indent=2))
                        print("=============================================\n")

                    elif chunk_type == "system":
                        runResults.chunk_counts.system += 1
                        runResults.total_system_messages += 1
                        print(
                            f"\n[SYSTEM] {chunk.get('content')} \n {chunk.get('error')}"
                        )

                    elif chunk_type == "error":
                        runResults.chunk_counts.error += 1
                        runResults.total_errors += 1
                        print(f"\n[ERROR] {chunk.get('content')}")
                        runResults.failed = True
                        runResults.error = str(chunk.get("content", "Unknown Error"))

                    else:
                        runResults.chunk_counts.unknown += 1
                        print(f"\n[UNKNOWN CHUNK] {chunk}")

            except Exception as e:
                print(f"\n[CRITICAL ERROR] Failed to run test {run_number}: {e}")
                runResults.failed = True
                runResults.error = str(e)
            finally:
                run_time_sec = time.time() - runStartTime
                runResults.end_time = time.strftime("%H:%M:%S", time.localtime(time.time()))
                runResults.run_time = format_duration(run_time_sec)

                # Compute per-day durations BEFORE reformatting the epoch fields
                # below (which would make subtraction impossible).
                day_times: list[float] = []
                for d_res in runResults.time_to_days_map.values():
                    if d_res.first_event_time and d_res.last_event_time:
                        d_run_time = max(
                            0.0,
                            float(d_res.last_event_time) - float(d_res.first_event_time),
                        )
                        d_res.day_run_time = format_duration(d_run_time)
                        day_times.append(d_run_time)

                if day_times:
                    runResults.average_day_time = format_duration(sum(day_times) / len(day_times))
                    runResults.fastest_day_time = format_duration(min(day_times))
                    runResults.slowest_day_time = format_duration(max(day_times))
                    runResults.median_day_time = format_duration(median(day_times))

                # Per-day event-gap aggregates.
                for d_num, d_res in runResults.time_to_days_map.items():
                    gaps = day_event_gaps.get(d_num, [])
                    if gaps:
                        d_res.average_event_time = format_duration(sum(gaps) / len(gaps))
                        d_res.fastest_event_time = format_duration(min(gaps))
                        d_res.slowest_event_time = format_duration(max(gaps))
                        d_res.median_event_time = format_duration(median(gaps))

                # Run-level event-gap aggregates.
                if event_gaps:
                    runResults.average_event_gap = format_duration(
                        sum(event_gaps) / len(event_gaps)
                    )
                    runResults.fastest_event_gap = format_duration(min(event_gaps))
                    runResults.slowest_event_gap = format_duration(max(event_gaps))
                    runResults.median_event_gap = format_duration(median(event_gaps))

                if runResults.days > 0:
                    runResults.average_events_per_day = round(
                        runResults.total_day_events / runResults.days, 2
                    )

                # Now convert first/last epoch → H:M:S strings for presentation.
                for d_res in runResults.time_to_days_map.values():
                    if d_res.first_event_time:
                        d_res.first_event_time = time.strftime(
                            "%H:%M:%S", time.localtime(float(d_res.first_event_time))
                        )
                    if d_res.last_event_time:
                        d_res.last_event_time = time.strftime(
                            "%H:%M:%S", time.localtime(float(d_res.last_event_time))
                        )

                testResults.run_results[run_number] = runResults

                if not runResults.failed:
                    testResults.successful_runs += 1
                    run_times.append(run_time_sec)
                else:
                    testResults.failed_runs += 1

            _write_results(results_file, testResults)

    testResults.end_time = time.strftime("%H:%M:%S", time.localtime(time.time()))
    testResults.test_time = format_duration(time.time() - testStartTime)
    if run_times:
        testResults.average_time = format_duration(sum(run_times) / len(run_times))
        testResults.fastest_time = format_duration(min(run_times))
        testResults.slowest_time = format_duration(max(run_times))
        testResults.median_time = format_duration(median(run_times))

    total_runs = testResults.successful_runs + testResults.failed_runs
    if total_runs > 0:
        testResults.success_rate = round(testResults.successful_runs / total_runs, 4)

    total_days_all = 0
    total_day_events_all = 0
    for rr in testResults.run_results.values():
        testResults.total_events_all_runs += rr.total_events
        testResults.total_tool_calls_all_runs += rr.total_tool_calls
        testResults.total_pruning_events_all_runs += rr.total_pruning_events
        testResults.total_pruning_drops_all_runs += rr.total_pruning_drops
        testResults.total_errors_all_runs += rr.total_errors
        total_days_all += rr.days
        total_day_events_all += rr.total_day_events
        for tool_name, count in rr.tool_usage.items():
            testResults.aggregate_tool_usage[tool_name] = (
                testResults.aggregate_tool_usage.get(tool_name, 0) + count
            )

    if total_runs > 0:
        testResults.average_days_per_trip = round(total_days_all / total_runs, 2)
        testResults.average_tool_calls_per_run = round(
            testResults.total_tool_calls_all_runs / total_runs, 2
        )
    if total_days_all > 0:
        testResults.average_events_per_day_all_runs = round(
            total_day_events_all / total_days_all, 2
        )

    end_ts = format_timestamp(time.time())
    print(f"------------------- Test completed at {end_ts} -------------------")
    print(f"-------------------------- Test results saved to {test_results_folder} ---------------------------")
    _write_results(results_file, testResults)


if __name__ == "__main__":
    asyncio.run(run_test())
