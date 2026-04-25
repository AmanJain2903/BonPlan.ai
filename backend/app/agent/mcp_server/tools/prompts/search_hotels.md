# search_hotels

Hotels around a coordinate for given check-in/out dates.

### When to use
- You need accommodations for a stay. Always pair with `get_hotel_booking_url` for the final booking URL.

### Arguments
- **`searchCoordinates`** (required): `{ latitude, longitude, radiusKm }`.
- **`checkinDate`** / **`checkoutDate`** (str `YYYY-MM-DD`, required).
- **`rooms`** (int 1..30, optional): default 1.
- **`adults`** (int 1..30, optional): default 1.
- **`children`** (list[int], optional): each age 0..17.
- **`minPrice`** / **`maxPrice`** (int USD, optional).
- **`resultsPerPage`** (int 5..50, optional): page size. Default 10.
- **`page`** (int, optional): 1-based. Default 1.
- **`units`** (`METRIC`|`IMPERIAL`, optional): default `IMPERIAL`.
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
`{ nbRooms, nbAdults, nbChildren, lengthOfStayInDays, checkinDate, checkoutDate, hotels: [{ propertyInfo, checkInOutInfo, priceInfo, isSoldOut }] }`

### Notes
- For more options, re-call with the same args and incremented `page`.
