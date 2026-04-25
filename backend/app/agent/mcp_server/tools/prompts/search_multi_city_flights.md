# search_multi_city_flights

Flights across multiple sequential legs (A→B, B→C, C→A).

### When to use
- Itinerary visits 3+ cities with distinct flight segments. For 2-city round-trips use `search_flights` with `return_date`.

### Arguments
- **`legs`** (list[FlightLeg], required): each leg is `{ departure_id, arrival_id, date }` (`YYYY-MM-DD`).
- **`passengers`** (optional): `{ adults, children, infant_on_lap, infant_in_seat }`. Default `{adults:1}`.
- **`travel_class`** (`ECONOMY`|`PREMIUM_ECONOMY`|`BUSINESS`|`FIRST`, optional): default `ECONOMY`.
- **`search_type`** (`best`|`cheap`, optional).
- **`return_type`** (`topFlights`|`otherFlights`|`all`, optional): default `topFlights`.
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
`{ topFlights: [...], otherFlights: [...] }` where each option's `flightItinerary` spans the first leg only. Each option carries a `nextToken`.

### Notes
- Each option returns one leg at a time. Walk forward with `get_next_flights(nextToken)` until a leg returns a `bookingToken`; then call `get_flight_booking_details`.
- **Never pass a `nextToken` to `get_flight_booking_details`.**
