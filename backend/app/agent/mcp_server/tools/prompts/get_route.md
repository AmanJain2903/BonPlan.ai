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
- **`intermediate_waypoints`** (list[Waypoint], optional): ordered stops. Must be less than 11 waypoints.
- **`travel_mode`** (`DRIVE`|`WALK`|`BICYCLE`|`TRANSIT`, optional): default `DRIVE`.
- **`routing_preference`** (`TRAFFIC_AWARE`|`TRAFFIC_UNAWARE`|`TRAFFIC_AWARE_OPTIMAL`, optional): DRIVE only. Default `TRAFFIC_AWARE`.
- **`departure_time`** (str ISO 8601 UTC, optional): must be in the future.
- **`route_modifiers`** (optional): e.g. `{ avoidHighways: true, avoidTolls: false }`.
- **`units_system`** (`IMPERIAL`|`METRIC`, optional): default `IMPERIAL`.
- **`compute_alternative_routes`** (bool, optional): default true.
- **`optimize_waypoint_order`** (bool, optional): default true.
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
`{ routes: [{ distance, durationWithTraffic, durationWithoutTraffic, routeLegs, mapsUrl, warnings, travelAdvisory, optimizedRoute? }] }`

### Selecting the Right Route

When the trip request names a specific road, highway, or scenic route as a preferred corridor:
1. Inspect the `description` field of every returned route for that road name. Prefer the matching route even if it is longer or slower than the default.
2. If no returned route's `description` contains the named road, re-call with `avoidHighways: true` inside `route_modifiers` — scenic and coastal roads are more likely to surface when freeways are excluded.
3. From the second call, pick the route whose `description` best matches the named road. If still no match, use the closest scenic alternative and note the discrepancy.
