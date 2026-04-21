# backend/app/agent/mcp_server/tools/_shared.py

"""
Shared primitives used by multiple MCP tools.

Kept private (underscore-prefixed) so FastMCP's auto-discovery on the
package doesn't try to register these as tools.
"""

from typing import Optional, Union

from pydantic import BaseModel, Field


class Waypoint(BaseModel):
    """
    Canonical flat waypoint shape used by `get_route` and `get_route_matrix`.

    Supply exactly one of:
    - ``address``: freeform address or place name — Google will geocode it.
    - ``lat`` AND ``lng``: exact coordinates (both must be provided together).
    - ``place_id``: a Google Place ID from ``search_places`` /
      ``search_places_nearby``.

    This replaces the previous ``Union[LocationFormat, PlaceIdFormat,
    AddressFormat]`` shape which was silently collapsed by the Gemini schema
    conversion (only the first ``anyOf`` branch was kept), causing silent
    MALFORMED_FUNCTION_CALL failures when the model passed an address or
    place_id form.
    """

    address: Optional[str] = Field(
        default=None,
        description=(
            "(Optional) Freeform address or place name, e.g. '1600 Amphitheatre Pkwy, "
            "Mountain View, CA' or 'Taj Mahal'. Google will geocode it."
        ),
    )
    lat: Optional[float] = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="(Optional) Latitude in decimal degrees. Provide together with `lng`.",
    )
    lng: Optional[float] = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="(Optional) Longitude in decimal degrees. Provide together with `lat`.",
    )
    place_id: Optional[str] = Field(
        default=None,
        description=(
            "(Optional) Google Place ID (from search_places / search_places_nearby). "
            "Mutually exclusive with address/lat/lng."
        ),
    )


async def normalize_waypoint(w: Union["Waypoint", dict]) -> dict:
    """
    Convert a ``Waypoint`` (or a dict in the flat shape) into the Google
    Routes API's expected waypoint body shape:

    - ``{"placeId": "ChIJ..."}``                   — when ``place_id`` supplied
    - ``{"location": {"latLng": {...}}}``          — when ``lat`` and ``lng`` supplied
    - ``{"address": "..."}``                       — when ``address`` supplied

    Precedence mirrors specificity: ``place_id`` > ``lat``/``lng`` > ``address``.
    Raises ``ValueError`` when none of the three is populated.
    """
    if isinstance(w, Waypoint):
        payload = w.model_dump(exclude_none=True)
    elif isinstance(w, dict):
        payload = {k: v for k, v in w.items() if v is not None}
    else:
        raise ValueError(
            "Waypoint must be a dict or Waypoint instance."
        )

    if payload.get("place_id"):
        return {"placeId": payload["place_id"]}
    if payload.get("lat") is not None and payload.get("lng") is not None:
        return {
            "location": {
                "latLng": {
                    "latitude": float(payload["lat"]),
                    "longitude": float(payload["lng"]),
                }
            }
        }
    if payload.get("address"):
        return {"address": payload["address"]}
    raise ValueError(
        "Waypoint must specify at least one of: address, (lat & lng), place_id."
    )


async def waypoint_validation_error(field_name: str, received: dict) -> dict:
    """
    Uniform actionable error returned when a waypoint is unusable. The
    agent runtime surfaces this verbatim to the model's next turn, so the
    ``fix_hint`` text is what the model reads and reacts to.
    """
    return {
        "error": f"Invalid waypoint provided for `{field_name}`.",
        "fix_hint": (
            "Each waypoint must specify ONE of: `address` (string), both "
            "`lat` and `lng` (floats), or `place_id` (Google Place ID string). "
            "If you only have a city name, call get_coordinates first to get "
            "coordinates, then pass {lat, lng}."
        ),
        "received": received,
    }

async def parse_mcp_location(loc: dict) -> tuple[str, str]:
    """
    Parses a Google-shaped waypoint dict (produced by `normalize_waypoint`)
    into a (String_Query, Place_ID) tuple for building maps URLs.
    Google Maps URLs require a string query even if you provide a Place ID.
    """
    if "address" in loc:
        return loc["address"], ""

    elif "location" in loc:
        lat = loc["location"]["latLng"]["latitude"]
        lng = loc["location"]["latLng"]["longitude"]
        return f"{lat},{lng}", ""

    elif "placeId" in loc:
        return "Saved Location", loc["placeId"]

    return "", ""
