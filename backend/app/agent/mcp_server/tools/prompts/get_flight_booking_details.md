# get_flight_booking_details

## Purpose
Retrieves the available booking packages (e.g., economy, premium) and pricing details for a specific flight itinerary. 

## When to use
Use this tool **after** obtaining a `booking_token`. 
- For one-way flights, obtain the `booking_token` directly from `search_flights` or `search_multi_city_flights`.
- For round-trip or multi-city itineraries, obtain the `booking_token` from the final `get_next_flights` call.

**CRITICAL WARNING:** NEVER pass a `nextToken` to this tool. It will fail. If you only have a `nextToken` from a previous flight search, you MUST pass that `nextToken` to `get_next_flights` to fetch the remaining flight legs and ultimately get the final `booking_token` before you can call this tool.

This tool tells you the different cabin options and packages. **The cost returned finally to the user must be the one from here.**

## Arguments
- `booking_token` (str): The booking token attached to the selected flight itinerary.
- `timeout_seconds` (int): (Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout. Default is 10 seconds.
  - Example: `15`

## Returns
- A list of `booking_options` containing `cabin`, `website`, `priceInUSD`, `baggageOptions`, `fareType`, and a `token`. You MUST use the `token` from your chosen package to call `get_flight_booking_url`.
