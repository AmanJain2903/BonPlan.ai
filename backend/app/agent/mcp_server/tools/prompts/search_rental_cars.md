# search_rental_cars

Rental cars for given pick-up / drop-off coordinates, dates, and times.

### When to use
- Driving-based trip and the user needs a car. Emit as CAR_PICKUP / CAR_DROPOFF events using the `bookingUrl` returned here.

### Arguments
- **`pickupCoordinates`** (required): `{ latitude, longitude }`.
- **`pickupDateTime`** (required): `{ date: "YYYY-MM-DD", time: "HH:MM" }` (local time at pickup).
- **`dropOffDateTime`** (required): same shape (local time at drop-off).
- **`dropOffCoordinates`** (optional): defaults to pickup location.
- **`sortBy`** (`recommended`|`price_low_to_high`, optional): default `recommended`.
- **`carTypes`** (list from `small`|`medium`|`large`|`estate`|`premium`|`carriers`|`suvs`, optional).
- **`driverAge`** (int, optional).
- **`units`** (`METRIC`|`IMPERIAL`, optional): default `IMPERIAL`.
- **`resultsPerPage`** (int 5..50, optional): default 10.
- **`page`** (int, optional): 1-based. Default 1.
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
`{ totalResults, totalPages, page, searchContext, rentalCarOptions: [{ supplierInfo, vehicleInfo, routeInfo, ratingInfo, pricingInfo, bookingUrl }], hasMorePages, nextPage }`

### Notes
- Paginate via `page = nextPage` while `hasMorePages` is true.
