# get_flight_booking_url

Final bookable URL for a selected flight package.

### When to use
- After `get_flight_booking_details` returned a package `token` and you need the URL for the itinerary event.

### Arguments
- **`token`** (str, required): package `token` from `get_flight_booking_details`.
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
`{ booking_url: str }`.

### Notes
- If this fails, fall back to the package's `website` field from `get_flight_booking_details`, or emit an empty string.
