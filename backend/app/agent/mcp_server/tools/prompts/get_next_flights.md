# get_next_flights

Fetch the next leg of a multi-leg flight search using a `nextToken`.

### When to use
- After `search_flights` (round-trip) or `search_multi_city_flights` returned a `nextToken` for your chosen outbound option.
- Keep calling with each new `nextToken` until a result carries a `bookingToken`.

### Arguments
- **`next_token`** (str, required): the `nextToken` from the prior search or `get_next_flights` call.
- **`return_type`** (`topFlights`|`otherFlights`|`all`, optional): default `topFlights`.
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
`{ topFlights: [...], otherFlights: [...] }`. Final leg → each option has a `bookingToken` (feed to `get_flight_booking_details`). Non-final leg → each option has another `nextToken`.
