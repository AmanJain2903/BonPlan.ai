import os
from typing import Dict, List, Tuple
from google.genai import types
from app.agent.schemas.structuredOutput import (
    AddItineraryEvent,
    StartEventDetails,
    FlightTakeoffEventDetails,
    FlightLandEventDetails,
    HotelCheckinEventDetails,
    HotelCheckoutEventDetails,
    CarPickupEventDetails,
    CarDropoffEventDetails,
    PlaceEventDetails,
    CommuteEventDetails,
    OtherEventDetails,
    EndEventDetails,
)
from app.logging import get_agent_logger

logger = get_agent_logger("helpers.utils")


def fix_schema_for_gemini(schema: dict) -> dict:
    import copy
    schema = copy.deepcopy(schema)
    defs = schema.pop("$defs", {})
    def process_node(node):
        if isinstance(node, dict):
            # Resolve $ref
            if "$ref" in node:
                ref_key = node["$ref"].split("/")[-1]
                resolved = process_node(defs[ref_key])
                for k, v in resolved.items():
                    node[k] = v
                del node["$ref"]
            # Fix anyOf
            if "anyOf" in node:
                non_nulls = [n for n in node["anyOf"] if n.get("type") != "null"]
                if non_nulls:
                    picked = non_nulls[0]
                    if "$ref" in picked:
                        ref_key = picked["$ref"].split("/")[-1]
                        resolved = process_node(defs[ref_key])
                        for k, v in resolved.items():
                            if k not in node:
                                node[k] = v
                    else:
                        picked = process_node(picked)
                        for k, v in picked.items():
                            if k not in node:
                                node[k] = v
                del node["anyOf"]
            # Strip unsupported keys
            for unsupported in ["additionalProperties", "additional_properties"]:
                if unsupported in node:
                    del node[unsupported]
            if "title" in node and isinstance(node["title"], str):
                del node["title"]
            if "default" in node:
                del node["default"]

            # Process remaining items recursively
            for k, v in list(node.items()):
                if k not in ["$ref", "anyOf"]:
                    node[k] = process_node(v)
            return node
        elif isinstance(node, list):
            return [process_node(v) for v in node]
        return node
    return process_node(schema)

def _load_add_event_description() -> str:
    path = os.path.join(os.path.dirname(__file__), "add_event.md")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        logger.warning("Failed to load add_event.md. Returning fallback description.")
        return "Call this tool to commit a specific event (Flight, Hotel, etc.) to the user's itinerary. The agent must call this multiple times to build a full trip. Be mindful for the format you are passing in the arguments. It is a nested JSON object with the keys and values as per the schema."

ADD_EVENT_TOOL = types.FunctionDeclaration(
    name="add_itinerary_event",
    description=_load_add_event_description(),
    # This ensures Gemini treats the arguments as a strictly structured JSON object
    parameters=fix_schema_for_gemini(AddItineraryEvent.model_json_schema())
)

def convert_mcp_to_gemini(mcp_tool) -> types.FunctionDeclaration:
    return types.FunctionDeclaration(
        name=mcp_tool.name,
        description=mcp_tool.description or "",
        parameters=fix_schema_for_gemini(mcp_tool.inputSchema)
    )


# ─────────────────────────────────────────────────────────────────────────────
# Per-event-type tools.
#
# Instead of one ~46 KB `add_itinerary_event` tool whose schema carries all 11
# optional `*_details` sub-objects every turn, we expose 10 small tools, each
# carrying only the sub-schema for one event type.  The dispatcher in
# gemini_adapter.py maps each tool name back to a unified `AddItineraryEvent`
# payload and runs the existing validator, so the frontend event chunk shape
# is untouched.
#
# TOOL_NAME_TO_EVENT_TYPE[tool_name]:
#   - str  → tool always emits this event_type (dispatcher injects it)
#   - None → tool accepts multiple event_types; the model must specify in args
# ─────────────────────────────────────────────────────────────────────────────

# Pull the top-level AddItineraryEvent property descriptions once so the
# per-type tools stay in lock-step with structuredOutput.py.
_BASE_ITINERARY_SCHEMA = fix_schema_for_gemini(AddItineraryEvent.model_json_schema())
_TOP_LEVEL_FIELDS = ("day_number", "day_title", "date", "event_number")


def _top_level_props() -> dict:
    return {k: dict(_BASE_ITINERARY_SCHEMA["properties"][k]) for k in _TOP_LEVEL_FIELDS}


def _build_event_tool(
    name: str,
    description: str,
    event_types: List[str],
    detail_field: str,
    details_model,
) -> types.FunctionDeclaration:
    details_schema = fix_schema_for_gemini(details_model.model_json_schema())
    props = _top_level_props()
    props["event_type"] = {
        "type": "string",
        "enum": list(event_types),
        "description": (
            f"The event type for this call. Must be one of: {event_types}."
        ),
    }
    props[detail_field] = details_schema

    parameters = {
        "type": "object",
        "properties": props,
        "required": list(_TOP_LEVEL_FIELDS) + ["event_type", detail_field],
    }
    return types.FunctionDeclaration(
        name=name,
        description=description,
        parameters=parameters,
    )


# (tool_name, description, [event_types], detail_field, DetailsModel)
_PER_TYPE_TOOL_SPECS: List[Tuple[str, str, List[str], str, type]] = [
    (
        "add_start_event",
        "Commit the START event for the trip (day_number=0, event_number=0). "
        "Emit this exactly once at the very beginning of the itinerary.",
        ["START"],
        "start_details",
        StartEventDetails,
    ),
    (
        "add_flight_takeoff_event",
        "Commit a flight takeoff event to the itinerary.",
        ["FLIGHT_TAKEOFF"],
        "flight_takeoff_details",
        FlightTakeoffEventDetails,
    ),
    (
        "add_flight_land_event",
        "Commit a flight landing event to the itinerary.",
        ["FLIGHT_LAND"],
        "flight_land_details",
        FlightLandEventDetails,
    ),
    (
        "add_hotel_checkin_event",
        "Commit a hotel check-in event to the itinerary.",
        ["HOTEL_CHECKIN"],
        "hotel_checkin_details",
        HotelCheckinEventDetails,
    ),
    (
        "add_hotel_checkout_event",
        "Commit a hotel check-out event to the itinerary.",
        ["HOTEL_CHECKOUT"],
        "hotel_checkout_details",
        HotelCheckoutEventDetails,
    ),
    (
        "add_car_pickup_event",
        "Commit a rental-car pickup event to the itinerary.",
        ["CAR_PICKUP"],
        "car_pickup_details",
        CarPickupEventDetails,
    ),
    (
        "add_car_dropoff_event",
        "Commit a rental-car dropoff event to the itinerary.",
        ["CAR_DROPOFF"],
        "car_dropoff_details",
        CarDropoffEventDetails,
    ),
    (
        "add_activity_or_dining_event",
        "Commit a DINING or ACTIVITY event to the itinerary. Both share the "
        "same place_details payload; set event_type accordingly.",
        ["DINING", "ACTIVITY"],
        "place_details",
        PlaceEventDetails,
    ),
    (
        "add_commute_event",
        "Commit a COMMUTE event (transit between two locations) to the itinerary.",
        ["COMMUTE"],
        "commute_details",
        CommuteEventDetails,
    ),
    (
        "add_other_event",
        "Commit an OTHER event (miscellaneous activity not covered by another "
        "event type) to the itinerary.",
        ["OTHER"],
        "other_details",
        OtherEventDetails,
    ),
    (
        "add_end_event",
        "Commit the END event for the trip (day_number=-1, event_number=-1). "
        "Emit this exactly once as the final event.",
        ["END"],
        "end_details",
        EndEventDetails,
    ),
]


PER_TYPE_EVENT_TOOLS: Dict[str, types.FunctionDeclaration] = {
    name: _build_event_tool(name, desc, evs, field, model)
    for (name, desc, evs, field, model) in _PER_TYPE_TOOL_SPECS
}

# tool_name → fixed event_type to inject, or None if the tool accepts multiple.
TOOL_NAME_TO_EVENT_TYPE: Dict[str, str | None] = {
    name: (evs[0] if len(evs) == 1 else None)
    for (name, _desc, evs, _field, _model) in _PER_TYPE_TOOL_SPECS
}

RESEARCH_EVENT_TOOL_NAMES: List[str] = ["add_start_event"]
DAY_EVENT_TOOL_NAMES: List[str] = [
    "add_flight_takeoff_event",
    "add_flight_land_event",
    "add_hotel_checkin_event",
    "add_hotel_checkout_event",
    "add_car_pickup_event",
    "add_car_dropoff_event",
    "add_activity_or_dining_event",
    "add_commute_event",
    "add_other_event",
]
FINALIZER_EVENT_TOOL_NAMES: List[str] = ["add_end_event"]


def build_phase_tool_block(
    mcp_tools: List[types.FunctionDeclaration],
    event_tool_names: List[str],
) -> types.Tool:
    """Compose MCP tools + the phase's per-type event tools into one Tool block."""
    decls = list(mcp_tools) + [PER_TYPE_EVENT_TOOLS[n] for n in event_tool_names]
    return types.Tool(function_declarations=decls)