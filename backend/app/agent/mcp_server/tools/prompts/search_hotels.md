# search_hotels

## Purpose
Searches for hotels and accommodations around a specific geographic coordinate within a given radius using the Booking.com RapidAPI.

## When to use
Use this tool when you need to find hotels, get property details, review ratings, check availability, or compare prices for a given stay.

## Arguments
- `searchCoordinates` (SearchCoordinates): The coordinates of the search location.
  - Example: `{"latitude": 40.7128, "longitude": -74.0060, "radiusKm": 5.0}`
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
- `minPrice` (int, optional): Minimum price in USD.
  - Example: `100`
- `maxPrice` (int, optional): Maximum price in USD.
  - Example: `500`
- `resultsPerPage` (int, optional): Per-request page size (5 to 50). This is the number of hotels returned in this single call, not a total cap. Default `10`.
  - Example: `20`
- `page` (int, optional): 1-based page number. Default `1`.
  - Example: `1`
- `units` (Literal["METRIC", "IMPERIAL"], optional): The units to use. Default "IMPERIAL".

## Pagination semantics
One call fetches up to `resultsPerPage` hotels for the given coordinates/dates. To walk more hotels, re-call with the same args but incremented `page` (1, 2, 3, ...).

## Returns
- **Success**: `{"nbRooms", "nbAdults", "nbChildren", "lengthOfStayInDays", "checkinDate", "checkoutDate", "hotels": [...]}`. Each hotel includes `propertyInfo`, `checkInOutInfo`, `priceInfo`, `rooms`, and `isSoldOut`.
- **Error**: `{"error", "fix_hint", ...}` — follow the `fix_hint` to correct your next call.
