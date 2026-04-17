# get_route

## Purpose
Calculates detailed directions, duration, polyline, and distance between one origin and one destination, optionally passing through intermediate waypoints, using Google Routes API.

## When to use
Use this tool when the user needs turn-by-turn or detailed travel directions, route alternatives, or an optimized driving path across specific locations.

## Waypoint shape
Every waypoint (origin, destination, and each intermediate) is a flat object that supplies ONE of these three forms:
- `{"address": "<freeform address or place name>"}` — Google will geocode it.
- `{"lat": <float>, "lng": <float>}` — exact coordinates. Both must be present together.
- `{"place_id": "<Google Place ID>"}` — a Place ID returned by `search_places` / `search_places_nearby`.

Never mix them in the same waypoint (e.g. don't send `address` AND `lat`). If you only have a city name and need coordinates later, call `get_coordinates` first.

## Arguments
- `origin` (Waypoint): The starting location.
  - Example: `{"address": "San Francisco, CA"}`
  - Example: `{"lat": 37.7749, "lng": -122.4194}`
- `destination` (Waypoint): The destination. Same shape as `origin`.
  - Example: `{"address": "San Jose, CA"}`
- `intermediate_waypoints` (List[Waypoint], optional): Ordered waypoints to pass through.
  - Example: `[{"address": "Palo Alto, CA"}, {"lat": 37.4419, "lng": -122.1430}]`
- `travel_mode` (Literal, optional): "DRIVE", "WALK", "BICYCLE", "TRANSIT", or "TWO_WHEELER". Default "DRIVE".
- `routing_preference` (Literal, optional): "TRAFFIC_AWARE", "TRAFFIC_UNAWARE", or "TRAFFIC_AWARE_OPTIMAL". Default "TRAFFIC_AWARE". Only applies for DRIVE / TWO_WHEELER.
- `departure_time` (str, optional): UTC ISO 8601 departure time (e.g. `"2026-04-14T20:00:00Z"`). Must be in the future.
- `route_modifiers` (RouteModifiers, optional): Avoidances, e.g. `{"avoidHighways": true, "avoidTolls": false}`.
- `units_system` (Literal, optional): "IMPERIAL" or "METRIC". Default "IMPERIAL".
- `compute_alternative_routes` (bool, optional): Return multiple route variations. Default true.
- `optimize_waypoint_order` (bool, optional): Let Google re-order intermediate waypoints for the shortest total trip. Default true. Set false to enforce strict visitation order.

## Returns
- **Success**: `{"routes": [...]}` — each route has `distance`, `durationWithTraffic`, `durationWithoutTraffic`, `routeLegs`, `mapsUrl`, `polyline`, `warnings`, `travelAdvisory`, and optionally `optimizedIntermediateWaypointIndex` + `optimizedRoute` if waypoint ordering was adjusted.
- **Error**: A dictionary with `error`, `fix_hint`, and optionally `status_code`. Use the `fix_hint` text to correct your next call.
