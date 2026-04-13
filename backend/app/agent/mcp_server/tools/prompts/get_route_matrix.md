# get_route_matrix

## Purpose
Computes the travel distance and duration (with and without traffic) for multiple origins to multiple destinations using the Google Routes API route matrix feature.

## When to use
Use this tool when you need to compare travel times and distances between a list of starting points and a list of ending points, especially when factoring in a specific travel mode, routing preference, or departure time.

## Arguments
- `origins` (List[WaypointFormat]): A list of objects containing route origins.
  - Example: `[{"waypoint": {"address": "San Francisco, CA"}}]`
- `destinations` (List[WaypointFormat]): A list of objects containing route destinations.
  - Example: `[{"waypoint": {"address": "Los Angeles, CA"}}]`
- `route_modifiers` (RouteModifiers, optional): Avoidances (tolls, highways, ferries).
  - Example: `{"avoidTolls": true}`
- `travel_mode` (Literal, optional): Travel mode (DRIVE, WALK, BICYCLE, TRANSIT, TWO_WHEELER). Default is "DRIVE".
  - Example: `"TRANSIT"`
- `routing_preference` (Literal, optional): Traffic consideration strategy. Default is "TRAFFIC_AWARE".
  - Example: `"TRAFFIC_AWARE"`
- `departure_time` (str, optional): Future departure time in UTC ISO 8601 string.
  - Example: `"2026-04-15T08:00:00Z"`
- `units_system` (Literal, optional): Distance output unit ("IMPERIAL" or "METRIC"). Default is "IMPERIAL".
  - Example: `"IMPERIAL"`

## Returns
- **Success**: A dictionary containing `routeMatrix`, an array of objects linking an origin to a destination with `distance`, `durationWithTraffic`, `durationWithoutTraffic`, `mapsUrl`, and other advisories.
- **Error**: A dictionary containing an `error` key.
