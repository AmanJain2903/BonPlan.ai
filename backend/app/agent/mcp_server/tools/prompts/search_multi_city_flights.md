# search_multi_city_flights

## Purpose
Searches for flights across multiple separate legs (a multi-city itinerary) using Google Flights API (via RapidAPI).

## When to use
Use this tool when a user is planning a trip that visits multiple destinations sequentially (e.g., JFK -> CDG, then CDG -> LHR, then LHR -> JFK). 

## Arguments
- `legs` (List[FlightLeg]): A list of objects specifying each flight leg.
  - Example: `[{"departure_id": "JFK", "arrival_id": "CDG", "date": "2026-06-01"}, {"departure_id": "CDG", "arrival_id": "LHR", "date": "2026-06-05"}]`
- `passengers` (Passengers): Passenger count dictionary. Defaults to 1 adult.
  - Example: `{"adults": 2, "children": 1, "infant_on_lap": 0, "infant_in_seat": 0}`
- `travel_class` (Literal, optional): Travel class (ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST). Default is ECONOMY.
  - Example: `"ECONOMY"`
- `search_type` (Literal, optional): Search type ('best' or 'cheap').
  - Example: `"best"`
- `return_type` (Literal, optional): Which flights to return ('topFlights', 'otherFlights', or 'all'). Default is 'topFlights'.
  - Example: `"topFlights"`

## Returns
- **Success**: Similar to regular flight search, returning `topFlights` and/or `otherFlights`, where the `flightItinerary` array spans the requested legs. Each flight option also contains a `bookingToken`, which is necessary for finalizing bookings. In some extended multi-city cases, a `nextToken` may also be provided on the root level to fetch further legs using the `get_next_flights` tool.
- **Error**: A dictionary containing an `error` key.
