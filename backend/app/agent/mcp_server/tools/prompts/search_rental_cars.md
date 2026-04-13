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
- `resultsPerPage` (int, optional): Results to return per page. Default is 10.
  - Example: `15`
- `page` (int, optional): Page number. Default is 1.
  - Example: `1`

## Returns
- **Success**: A dictionary containing `totalResults`, `rentalCarOptions` (includes `supplierInfo`, `vehicleInfo`, `routeInfo`, `ratingInfo`, `pricingInfo`, `bookingUrl`), `hasMorePages`, and `nextPage`. If `hasMorePages` is true, make another exact same call using `page` = `nextPage` to retrieve more cars.
- **Error**: A dictionary containing an `error` key with the cause of failure.
