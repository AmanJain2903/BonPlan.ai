# get_route

## Purpose
Calculates detailed directions, duration, polyline, and distance between one origin and one destination, optionally passing through intermediate waypoints, using Google Routes API.

## When to use
Use this tool when the user needs turn-by-turn or detailed travel directions, route alternatives, or an optimized driving path across specific locations.

## Arguments
- `origin` (WaypointType): The starting location.
  - Example: `{"address": "San Francisco"}`
- `destination` (WaypointType): The destination.
  - Example: `{"address": "San Jose"}`
- `intermediate_waypoints` (List[WaypointType], optional): Waypoints to pass through.
  - Example: `[{"address": "Palo Alto"}]`
- `travel_mode` (Literal, optional): "DRIVE", "WALK", "BICYCLE", "TRANSIT", or "TWO_WHEELER". Default is "DRIVE".
  - Example: `"DRIVE"`
- `routing_preference` (Literal, optional): "TRAFFIC_AWARE", "TRAFFIC_UNAWARE", or "TRAFFIC_AWARE_OPTIMAL". Default is "TRAFFIC_AWARE".
  - Example: `"TRAFFIC_AWARE"`
- `departure_time` (str, optional): UTC ISO 8601 departure time.
  - Example: `"2026-04-14T20:00:00Z"`
- `route_modifiers` (RouteModifiers, optional): Avoidances.
  - Example: `{"avoidHighways": true}`
- `units_system` (Literal, optional): Distance units. Default is "IMPERIAL".
  - Example: `"IMPERIAL"`
- `compute_alternative_routes` (bool, optional): Determine if alternatives are provided. Default is True.
  - Example: `True`
- `optimize_waypoint_order` (bool, optional): Allow the API to reorder intermediate waypoints. Default is True.
  - Example: `False`

## Returns
- **Success**: A dictionary containing `routes`, a list of computed paths, showing `distance`, `durationWithTraffic`, `durationWithoutTraffic`, `routeLegs`, `mapsUrl`, and optionally `optimizedIntermediateWaypointIndex` if intermediate paths are optimized.
- **Error**: A dictionary containing an `error` key.
