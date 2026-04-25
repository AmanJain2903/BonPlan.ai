# get_flight_booking_details

Booking packages + final pricing for a selected flight itinerary.

### When to use
- After the final leg of a flight search returned a `bookingToken`.
- **The price used in the emitted event must come from here**, not from the initial search.

### Arguments
- **`booking_token`** (str, required): from the final `search_flights` / `search_multi_city_flights` / `get_next_flights` result.
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
`[ { cabin, website, priceInUSD, baggageOptions, fareType, token } ]` — each option's `token` feeds `get_flight_booking_url`.

### Notes
- **Never pass a `nextToken` here** — walk `get_next_flights` first until you have a true `bookingToken`.
