# get_next_flights

## Purpose
Retrieves the subsequent flights in a round-trip itinerary using a previously obtained `nextToken`.

## When to use
Use this tool specifically after calling `search_flights` with a `return_date`. The initial search might return an outbound flight and a `nextToken`. You must pass that `nextToken` to this tool to get the available return flights.

## Arguments
- `next_token` (str): The specific `nextToken` originally returned from a prior successful call to `search_flights` or `search_multi_city_flights`. This connects the subsequent return/next flight securely to the previously selected outbound flight.
  - Example: `"GgZDR0gSJ..."`
- `return_type` (Literal, optional): Which flights to return ('topFlights', 'otherFlights', or 'all'). Default is 'topFlights'.
  - Example: `"topFlights"`
- `timeout_seconds` (int): (Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout. Default is 30 seconds.
  - Example: `35`

## Returns
- **Success**: A dictionary of the return flights grouped by `topFlights` and `otherFlights`. If this is the final leg of the flight itinerary, each flight option will contain a `bookingToken` to fetch booking information by calling `get_flight_booking_details`. If there are still more legs, it will contain a `nextToken` instead, which you must use to fetch further legs using the `get_next_flights` tool again.
- **Error**: A dictionary containing an `error` key.
