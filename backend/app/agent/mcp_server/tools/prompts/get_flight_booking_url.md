# get_flight_booking_url

## Purpose
Retrieves the final URL required to book the selected flight package.

## When to use
Use this tool **after** calling `get_flight_booking_details` and selecting a specific flight package (e.g., standard economy vs basic economy). Pass the `token` from your selected package into this tool.

If this tool fails or does not return a booking URL, fallback to the `website` field returned by `get_flight_booking_details` for that package, or output an empty string.

## Arguments
- `token` (str): The token associated with the specific booking package from `get_flight_booking_details`.
- `timeout_seconds` (int): (Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout. Default is 5 seconds.
  - Example: `10`

## Returns
- A `booking_url` string which you can provide to the user to finalize their booking.
