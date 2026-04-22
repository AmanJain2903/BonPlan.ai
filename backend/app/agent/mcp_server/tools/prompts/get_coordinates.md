# get_coordinates

Geocode an address or place name to `(lat, lng, place_id)`.

### When to use
- You have a free-form location string and need numeric coordinates or a Google `place_id` to feed into another tool (weather, nearby search, routing).

### Arguments
- **`address`** (str, required): Street address, landmark, or city/region — e.g. `"Paris, France"` or `"1 Infinite Loop, Cupertino, CA"`.
- **`timeout_seconds`** (int, optional): Only raise if a prior call timed out.

### Returns
`{ address: <formal formatted>, lat: float, lng: float, place_id: str }`
