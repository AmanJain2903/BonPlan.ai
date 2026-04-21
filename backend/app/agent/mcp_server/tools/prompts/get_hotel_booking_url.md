# get_hotel_booking_url

## Purpose
Retrieves the booking URL for a specific hotel property using its ID and stay details via the Booking.com RapidAPI.

## When to use
Use this tool **after** obtaining a `propertyId` from `search_hotels`. 
Call this when the user needs a direct link to finalize their accommodation booking.

## Arguments
- `hotel_id` (str): The ID of the hotel to get the booking URL for (this corresponds to `propertyId` from `search_hotels`).
  - Example: `"1234567"`
- `checkinDate` (str): The check-in date in 'YYYY-MM-DD' format.
  - Example: `"2026-05-15"`
- `checkoutDate` (str): The check-out date in 'YYYY-MM-DD' format.
  - Example: `"2026-05-20"`
- `rooms` (int, optional): The number of rooms to search for. Ranging from 1 to 30. Default is 1.
  - Example: `1`
- `adults` (int, optional): The number of adults. Ranging from 1 to 30. Default is 1.
  - Example: `2`
- `children` (List[int], optional): List of children ages. Ranging from 0 to 17. Default is None.
  - Example: `[5, 12]`
- `units` (Literal["metric", "imperial"], optional): The units to use. Default "imperial".
- `timeout_seconds` (int, optional): Timeout in seconds for the tool execution. Only increase this if a previous call failed due to timeout. Default is 10 seconds.
  - Example: `15`

## Returns
- **Success**: `{"booking_url": "https://..."}`. Provides the direct URL to the booking page.
- **Error**: `{"error", "fix_hint", ...}` — follow the `fix_hint` to correct your next call.
