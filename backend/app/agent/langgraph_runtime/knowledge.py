"""
End-of-day handoff-note extraction.

Each day planner finishes with a local chat history full of tool responses
(hotel search results, flight results, rental-car terms, place-info pages)
that informed its decisions. Those responses vanish when the next day starts
with a fresh chat, but the information they carry — checkout policies,
round-trip coverage, fuel rules, booking-token expiry — is exactly what the
next planner needs so it doesn't rebook what's already arranged.

`extract_handoff_notes` takes the events emitted this day + snapshots of
search-tool responses and asks the (cheap) pruning model to produce a small
JSON array of durable notes. These are appended to `PlannerState.shared_notes`
and injected into every subsequent day's prompt (and the finalizer's prompt).

Output per note:
    {
        "day_number_added": int,
        "scope": "hotel:Marriott Marquis" | "flight:UA1234" | "car:Hertz-SFO" | "general",
        "topic": "checkout_policy" | "round_trip" | "fuel_policy" | ...,
        "text": "Checkout by 11:00 AM; late checkout billed $50."
    }
"""
import json
from typing import Any, Dict, List

from app.logging import get_agent_logger
from app.agent.core.runtime import runtime
from app.core.config import settings

log = get_agent_logger("knowledge")
_MODEL = settings.CONTEXT_PRUNING_MODEL

_MAX_FINDINGS_CONSIDERED = 12
_MAX_FINDING_RESPONSE_CHARS = 2500
_MAX_NOTES_PER_DAY = 20


def _compact_events(events: List[Dict[str, Any]]) -> str:
    return json.dumps(
        [
            {
                "day_number": e.get("day_number"),
                "event_number": e.get("event_number"),
                "event_type": e.get("event_type"),
                "event_name": e.get("event_name"),
            }
            for e in events
        ],
        default=str,
    )


def _compact_findings(findings: List[Dict[str, Any]]) -> str:
    chunks: List[str] = []
    for f in findings[-_MAX_FINDINGS_CONSIDERED:]:
        try:
            args_str = json.dumps(f.get("args") or {}, default=str)[:400]
        except Exception:
            args_str = ""
        resp = str(f.get("response") or "")[:_MAX_FINDING_RESPONSE_CHARS]
        chunks.append(f"[{f.get('tool')}]\nargs={args_str}\nresponse={resp}")
    return "\n\n".join(chunks)


def _strip_code_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("```", 2)[1] if "```" in t[3:] else t[3:]
        if t.lower().startswith("json"):
            t = t[4:]
    return t.strip()


def _parse_notes_payload(text: str, day_number: int) -> List[Dict[str, Any]]:
    cleaned = _strip_code_fences(text)
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except Exception:
        return []
    if not isinstance(parsed, list):
        return []

    out: List[Dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        scope = str(item.get("scope") or "").strip()
        topic = str(item.get("topic") or "").strip()
        text = str(item.get("text") or "").strip()
        if not (scope and topic and text):
            continue
        out.append({
            "day_number_added": day_number,
            "scope": scope[:120],
            "topic": topic[:60],
            "text": text[:400],
        })
        if len(out) >= _MAX_NOTES_PER_DAY:
            break
    return out


async def extract_handoff_notes(
    *,
    day_number: int,
    session_events: List[Dict[str, Any]],
    tool_findings: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Promote policy/coverage facts from search-tool responses into structured
    handoff notes. Returns [] on any failure — never raises.
    """
    client = runtime.pruning_client
    if client is None or not tool_findings or not session_events:
        return []

    prompt = (
        "You are extracting durable handoff notes from ONE day of a multi-day "
        "travel-planning conversation. These notes will be injected into the "
        "next day's planner so it does not re-derive or re-book what is "
        "already arranged.\n\n"
        "Events emitted on this day (authoritative — do NOT repeat their core "
        "content in notes; only add information the events themselves do not "
        "carry):\n"
        f"{_compact_events(session_events)}\n\n"
        "Search-tool responses the day planner consulted (policies / "
        "round-trip coverage / booking tokens live here):\n"
        f"{_compact_findings(tool_findings)}\n\n"
        "Extract ONLY facts that future days need but cannot read off the "
        "emitted events. Good examples:\n"
        "- hotel checkout time + late-checkout rule\n"
        "- hotel early-check-in policy\n"
        "- round-trip flight coverage (state clearly that the return leg is "
        "already booked as part of the outbound ticket, with flight number/"
        "date/time — so the return-day planner DOES NOT rebook and just outputs the event)\n"
        "- included return leg details when round-trip\n"
        "- car rental fuel / mileage / drop-off location policy\n"
        "- car rental return time cut-off\n"
        "Output STRICT JSON: an array of objects with keys "
        '{"scope","topic","text"}. '
        '"scope" is a short label like "hotel:Marriott Marquis", '
        '"flight:UA1234", "car:Hertz-SFO", or "general". '
        '"topic" is one tag: checkout_policy, early_checkin, round_trip, '
        'return_leg, fuel_policy, mileage_policy, dropoff_policy, '
        'booking_expiry, confirmation_pickup, reservation_hold. '
        '"text" is ONE concise sentence in English. '
        "Return [] if there is nothing durable. Do not invent facts."
    )
    try:
        resp = await client.aio.models.generate_content(
            model=_MODEL, contents=prompt,
        )
        text = (getattr(resp, "text", None) or "").strip()
        if not text:
            return []
        return _parse_notes_payload(text, day_number)
    except Exception as e:
        log.warning("Handoff-note extraction failed", error=str(e))
        return []


def render_shared_notes(notes: List[Dict[str, Any]]) -> str:
    """Format shared_notes for inclusion in a prompt. Empty → placeholder."""
    if not notes:
        return "(none)"
    by_scope: Dict[str, List[Dict[str, Any]]] = {}
    for n in notes:
        by_scope.setdefault(n.get("scope") or "general", []).append(n)
    lines: List[str] = []
    for scope, entries in by_scope.items():
        lines.append(f"• {scope}")
        for n in entries:
            topic = n.get("topic") or ""
            text = n.get("text") or ""
            day = n.get("day_number_added")
            lines.append(f"    - [{topic}] {text} (added on day {day})")
    return "\n".join(lines)
