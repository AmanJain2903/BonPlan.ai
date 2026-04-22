# get_route

Detailed directions, duration, and distance for one origin → destination (with optional intermediate waypoints).

### When to use
- You are confirming a single COMMUTE leg (distance, duration with traffic, maps URL).
- For a full many-to-many matrix use `get_route_matrix`. For a visit-order hint use `get_optimal_route`.

### Waypoint shape
Each waypoint uses exactly ONE of:
- `{ "address": "<free text>" }` (geocoded)
- `{ "lat": <float>, "lng": <float> }` (both required)
- `{ "place_id": "<Google Place ID>" }`

### Arguments
- **`origin`** (Waypoint, required).
- **`destination`** (Waypoint, required).
- **`intermediate_waypoints`** (list[Waypoint], optional): ordered stops.
- **`travel_mode`** (`DRIVE`|`WALK`|`BICYCLE`|`TRANSIT`|`TWO_WHEELER`, optional): default `DRIVE`.
- **`routing_preference`** (`TRAFFIC_AWARE`|`TRAFFIC_UNAWARE`|`TRAFFIC_AWARE_OPTIMAL`, optional): DRIVE/TWO_WHEELER only. Default `TRAFFIC_AWARE`.
- **`departure_time`** (str ISO 8601 UTC, optional): must be in the future.
- **`route_modifiers`** (optional): e.g. `{ avoidHighways: true, avoidTolls: false }`.
- **`units_system`** (`IMPERIAL`|`METRIC`, optional): default `IMPERIAL`.
- **`compute_alternative_routes`** (bool, optional): default true.
- **`optimize_waypoint_order`** (bool, optional): default true.
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
`{ routes: [{ distance, durationWithTraffic, durationWithoutTraffic, routeLegs, mapsUrl, warnings, travelAdvisory, optimizedRoute? }] }`
