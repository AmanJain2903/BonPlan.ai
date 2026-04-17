# get_route_matrix

## Purpose
Computes travel distance and duration (with and without traffic) for every origin-to-destination pair across two lists using the Google Routes API route-matrix endpoint. Up to 625 total combinations per call.

## When to use
Use this tool when you need to compare travel times and distances between a list of starting points and a list of ending points — e.g. picking the closest hotel from a set to a list of attractions.

## Waypoint shape
Every entry in `origins` and `destinations` is a flat object that supplies ONE of these three forms:
- `{"address": "<freeform address or place name>"}`
- `{"lat": <float>, "lng": <float>}` — both must be present together.
- `{"place_id": "<Google Place ID>"}`

Never mix fields inside one waypoint. Call `get_coordinates` first if you only have a city name and need exact lat/lng.

## Arguments
- `origins` (List[Waypoint]): Non-empty list of starting waypoints.
  - Example: `[{"address": "San Francisco, CA"}, {"lat": 37.3541, "lng": -121.9552}]`
- `destinations` (List[Waypoint]): Non-empty list of ending waypoints.
  - Example: `[{"address": "Los Angeles, CA"}, {"place_id": "ChIJE9on3F3HwoAR9AhGJW_fL-I"}]`
- `route_modifiers` (RouteModifiers, optional): Avoidances (tolls, highways, ferries). Only applies for DRIVE / TWO_WHEELER.
  - Example: `{"avoidTolls": true}`
- `travel_mode` (Literal, optional): "DRIVE", "WALK", "BICYCLE", "TRANSIT", or "TWO_WHEELER". Default "DRIVE".
- `routing_preference` (Literal, optional): "TRAFFIC_AWARE", "TRAFFIC_UNAWARE", or "TRAFFIC_AWARE_OPTIMAL". Default "TRAFFIC_AWARE". Only applies for DRIVE / TWO_WHEELER.
- `departure_time` (str, optional): Future UTC ISO 8601 departure time, e.g. `"2026-04-15T08:00:00Z"`.
- `units_system` (Literal, optional): "IMPERIAL" or "METRIC". Default "IMPERIAL".

## Returns
- **Success**: `{"routeMatrix": [...]}`. Each entry has `originIndex`, `destinationIndex` (back-references into the input lists), `origin`, `destination`, `distance`, `durationWithTraffic`, `durationWithoutTraffic`, `mapsUrl`, `routeCondition`, and advisories. Note: the matrix is flat — one entry per reachable pair.
- **Error**: A dictionary with `error`, `fix_hint`, and optionally `status_code`. Use the `fix_hint` to correct your next call.
