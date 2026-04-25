# get_hotel_booking_url

Direct bookable URL for a specific hotel property.

### When to use
- After `search_hotels` returned a `propertyId` you intend to emit as a HOTEL_CHECKIN event.

### Arguments
- **`hotel_id`** (str, required): the `propertyId` from `search_hotels`.
- **`checkinDate`** / **`checkoutDate`** (str `YYYY-MM-DD`, required): must match the original search.
- **`rooms`** (int 1..30, optional): default 1.
- **`adults`** (int 1..30, optional): default 1.
- **`children`** (list[int 0..17], optional).
- **`units`** (`metric`|`imperial`, optional): default `imperial`.
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
`{ booking_url: str }`.
