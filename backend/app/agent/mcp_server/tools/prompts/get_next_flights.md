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

## Returns
- **Success**: A dictionary of the return flights grouped by `topFlights` and `otherFlights`. Each flight option similarly contains a `bookingToken` to finalize the combined booking itinerary, or a `nextToken` to fetch further legs using the `get_next_flights` tool again.
- **Error**: A dictionary containing an `error` key.
