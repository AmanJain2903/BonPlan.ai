# get_route_matrix

Travel distance + duration for every origin↔destination pair across two lists (up to 625 pairs/call).

### When to use
- Picking the closest option from a set (e.g. nearest hotel across candidate attractions).
- Comparing commute costs before committing to a route.
- For a single leg use `get_route`.

### Waypoint shape
Same as `get_route`: exactly ONE of `address`, `{lat,lng}`, or `place_id` per entry.

### Arguments
- **`origins`** (list[Waypoint], required, non-empty).
- **`destinations`** (list[Waypoint], required, non-empty).
- **`travel_mode`** (`DRIVE`|`WALK`|`BICYCLE`|`TRANSIT`, optional): default `DRIVE`.
- **`routing_preference`** (optional): DRIVE only.
- **`departure_time`** (str ISO 8601 UTC, optional): must be in the future.
- **`route_modifiers`** (optional).
- **`units_system`** (`IMPERIAL`|`METRIC`, optional): default `IMPERIAL`.
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
`{ routeMatrix: [{ originIndex, destinationIndex, origin, destination, distance, durationWithTraffic, durationWithoutTraffic, mapsUrl, routeCondition }] }` — flat, one entry per reachable pair.
