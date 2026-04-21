# search_rental_cars

## Purpose
Searches for rental cars based on pick-up and drop-off coordinates, dates, times, and preferences using the Booking.com RapidAPI.

## When to use
Use this tool when finding available car rentals for a trip. It can return a list of car options, supplier details, vehicle specs, route instructions, and pricing.

## Arguments
- `pickupCoordinates` (Coordinates): Latitude and longitude of the pick-up location.
  - Example: `{"latitude": 40.6413, "longitude": -73.7781}`
- `pickupDateTime` (DateTime): Date and time for pick-up at the local time of the pick-up location.
  - Example: `{"date": "2026-06-10", "time": "10:00"}`
- `dropOffDateTime` (DateTime): Date and time for drop-off at the local time of the drop-off location.
  - Example: `{"date": "2026-06-15", "time": "14:00"}`
- `dropOffCoordinates` (Coordinates, optional): Coordinates of drop-off. If None, it assumes the drop-off location is the same as the pick-up.
  - Example: `{"latitude": 38.9072, "longitude": -77.0369}`
- `sortBy` (Literal, optional): Sort preference. Options: "recommended", "price_low_to_high". Default is "recommended".
  - Example: `"price_low_to_high"`
- `carTypes` (List[str], optional): A list specifying the types of vehicles to filter by. You can include multiple elements from the specific literal list: ["small", "medium", "large", "estate", "premium", "carriers", "suvs"].
  - Example: `["suvs", "premium"]`
- `driverAge` (int, optional): Age of the driver.
  - Example: `30`
- `units` (Literal["METRIC", "IMPERIAL"], optional): The distance units. Default is "IMPERIAL".
  - Example: `"METRIC"`
- `resultsPerPage` (int, optional): Per-request page size (5 to 50). This is the number of cars returned in one call, not a total cap. Default `10`.
  - Example: `15`
- `page` (int, optional): 1-based page number. Default `1`.
  - Example: `1`
- `timeout_seconds` (int, optional): Timeout in seconds for the tool execution. Only increase this if a previous call failed due to timeout. Default is `15`.
  - Example: `20`

## Pagination semantics
One call fetches up to `resultsPerPage` cars from the full result set starting at `(page - 1) * resultsPerPage`. To walk more cars for the same query, re-call with the same arguments but `page = nextPage` from the previous response, until `hasMorePages` is `false`.

## Returns
- **Success**: `{"totalResults", "totalPages", "page", "searchContext", "rentalCarOptions": [...], "hasMorePages", "nextPage"}`. Each entry in `rentalCarOptions` contains `supplierInfo`, `vehicleInfo`, `routeInfo`, `ratingInfo`, `pricingInfo`, and `bookingUrl`.
- **Error**: `{"error", "fix_hint", ...}`. Out-of-range `page` errors include `total_pages` so you can pick a valid page number.
