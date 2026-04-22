# search_flights

Flights between two airports on given dates (one-way or round-trip).

### When to use
- Standard point-to-point journey. For 3+ cities use `search_multi_city_flights`.

### Arguments
- **`departure_id`** / **`arrival_id`** (str IATA code, required).
- **`outbound_date`** (str `YYYY-MM-DD`, required).
- **`passengers`** (optional): `{ adults, children, infant_on_lap, infant_in_seat }`. Default `{adults:1}`.
- **`return_date`** (str `YYYY-MM-DD`, optional): supplying this triggers a round-trip search.
- **`travel_class`** (`ECONOMY`|`PREMIUM_ECONOMY`|`BUSINESS`|`FIRST`, optional): default `ECONOMY`.
- **`search_type`** (`best`|`cheap`, optional).
- **`return_type`** (`topFlights`|`otherFlights`|`all`, optional): default `topFlights`.
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
`{ topFlights: [...], otherFlights: [...] }` — each flight has `departureTime`, `arrivalTime`, `durationInMinutes`, `priceInUSD`, `flightItinerary`, `layovers`, `flight_type`.

### Notes
- One-way results carry `bookingToken` → use with `get_flight_booking_details`.
- Round-trip outbound results carry `nextToken` → use with `get_next_flights` to fetch the return leg. **Never pass `nextToken` to `get_flight_booking_details`.**
- On a round-trip, `priceInUSD` is the minimum total for that outbound paired with some return.
