# add_itinerary_event

## Purpose
Call this tool to commit a specific event (Flight, Hotel, Activity, Commute, etc.) to the user's itinerary. The agent must call this sequentially multiple times to build a full trip. Be mindful of the format you are passing in the arguments—it is a nested JSON object with keys and values following the required schemas.

## When to use
Use this tool *after* calling information retrieval tools (like `search_flights`, `search_hotels`, `search_places`, `get_route_matrix`, etc.) to definitively lock down a step of the user's journey. You build the trip event by event, day by day.

## Critical Rules & Constraints
1. **Lifecycle Constraints**: 
   - You **MUST** start the itinerary by logging a `START` event type, using day number `0` and event number `0`.
   - You **MUST** log regular events chronologically by event number (Event 1, Event 2, etc...) and day number (Day 1, Day 2, etc...) using standard event types.
   - You **MUST** complete the itinerary by logging a final `END` event type, using day number `-1` and event number `-1`. Failure to log the `END` event will break the itinerary.
2. **Strict Exclusivity**: You can only populate the specific details sub-object that matches your `event_type`. All other detail sub-objects MUST be omitted or set to null. For example, if `event_type` is `HOTEL_CHECKIN`, provide `hotel_checkin_details` and leave `flight_takeoff_details`, `commute_details`, etc., completely empty/null.
3. **Data Accuracy & Sourcing**: All IDs, URLs (including logos and booking URLs), coordinates, names, prices and all other factual info in the output MUST be exact matches to real data fetched from the tool calls. Do not hallucinate information.
4. **Time Formats**: 
   - Dates must be strictly formatted as `YYYY-MM-DD`. For `START` and `END` events, the date string should be strictly `"Start"` or `"End"` respectively.
   - Timestamps strictly formatted as `YYYY-MM-DDTHH:MM:SS` (representing the local time of the event's location).

## Common Fields Overview
- `day_number` (int): Day of the trip. (`0` for START, `1` for first day, `2` for second day, and increments sequentially, `-1` for END).
- `day_title` (str): Title for the day. (e.g. `Day 1 - Arrival in Paris`, `Start`, or `End`).
- `date` (str): Local date `YYYY-MM-DD`. (Use `"Start"` or `"End"` for START/END events respectively).
- `event_number` (int): Chronological order of the event within the day. (`1` for the first event of the day, increments sequentially. `0` for START, `-1` for END).
- `event_type` (str): Must be exactly one of: `START`, `FLIGHT_TAKEOFF`, `FLIGHT_LAND`, `HOTEL_CHECKIN`, `HOTEL_CHECKOUT`, `CAR_PICKUP`, `CAR_DROPOFF`, `DINING`, `ACTIVITY`, `COMMUTE`, `OTHER`, `END`.

## Guidance for Specialized Details
- **`START` and `END`**: Are high-level aggregations. The `START` block anticipates the trip scope, while the `END` block tallies total costs and generated tips.
- **Flights**: Must be broken into a `FLIGHT_TAKEOFF` event followed by a `FLIGHT_LAND` event.
- **Hotels**: Broken into `HOTEL_CHECKIN` and `HOTEL_CHECKOUT`. Populate the `cost` estimate accurately representing the entire stay duration on the checkin event.
- **Places (DINING / ACTIVITY / OTHER)**: Ensure accurate durations and timing. Provide robust generative properties like tips, summaries, and URLs derived from tool results. 
- **Commute/Transit**: Should be used to bridge gaps between other events (e.g., getting from the Airport to the Hotel, or between two separated Activities). Extract specific durations, distances, and mode of transit from Route APIs.

## Returns
- This tool does not return application data. It validates your payload against the strict Pydantic requirements and commits it to the database. If your call successfully succeeds, consider the event locked in and proceed to design the subsequent event. If you receive an error, carefully review the requested schema rules to debug and repair your API arguments.
