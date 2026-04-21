# search_flights

## Purpose
Searches for available flights between two specific airports on given dates, supporting both one-way and round-trip searches, using Google Flights API (via RapidAPI).

## When to use
Use this tool to find flight options, prices, airlines, and itineraries for a standard point-to-point journey. Note that to perform a round-trip search, simply supply a `return_date`.

## Arguments
- `departure_id` (str): Departure airport code.
  - Example: `"JFK"`
- `arrival_id` (str): Arrival airport code.
  - Example: `"LHR"`
- `outbound_date` (str): Departure date in 'YYYY-MM-DD' format.
  - Example: `"2026-08-10"`
- `passengers` (Passengers): Passenger count dictionary. Defaults to 1 adult.
  - Example: `{"adults": 1, "children": 0, "infant_on_lap": 0, "infant_in_seat": 0}`
- `return_date` (str, optional): Return date in 'YYYY-MM-DD' format.
  - Example: `"2026-08-20"`
- `travel_class` (Literal, optional): Travel class (ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST). Default is ECONOMY.
  - Example: `"BUSINESS"`
- `search_type` (Literal, optional): Search type ('best' or 'cheap').
  - Example: `"cheap"`
- `return_type` (Literal, optional): Which flights to return ('topFlights', 'otherFlights', or 'all'). Default is 'topFlights'.
  - Example: `"topFlights"`
- `timeout_seconds` (int): (Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout. Default is 20 seconds.
  - Example: `25`

## Returns
- **Success**: A dictionary separating `topFlights` and `otherFlights`. Each flight contains `departureTime`, `arrivalTime`, `durationInMinutes`, `priceInUSD`, `flightItinerary`, `layovers` and `flight_type`. For one-way flights, each flight will have a `bookingToken`, which you use to call `get_flight_booking_details`. For round-trip returns, the flights will NOT have a `bookingToken`. Instead, there will be a `nextToken` on each flight. You MUST use the `nextToken` to call `get_next_flights` to fetch the next leg. **DO NOT pass a `nextToken` to `get_flight_booking_details`, it will fail.** The `priceInUSD` here shows the minimum you can get for a round trip if you chose this as the first outbound leg.
- **Error**: A dictionary containing an `error` key.
