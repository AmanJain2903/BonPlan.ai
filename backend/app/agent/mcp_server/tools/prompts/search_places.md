# search_places

Find a real-world place (business, landmark, POI) from a free-text query.

### When to use
- You have a descriptive phrase but no coordinates or Place ID (e.g. `"pizza near Times Square"`, `"Eiffel Tower"`).
- For coordinate-centric searches prefer `search_places_nearby`.

### Arguments
- **`query`** (str, required): one subject + locality works best.
- **`max_results`** (int 1..10, optional): upstream page size. Default 5.
- **`place_index`** (int, optional): which place on the page to return. Default 0.
- **`nextPageToken`** (str, optional): fetch a further page (reset `place_index` to 0).
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
One `place` + `{ nextPageToken, hasNext, nextIndex }`. Place fields: `id`, `name`, `type`, `placeSummary`, `location`, `urls{googleMapsUrl,websiteUrl}`, `reviews`, `priceLevel`, `priceRange`, `openingHours`, `diningOptions`, `amenities`, `accessibilityOptions`, `businessStatus`.

### Notes
- Walk the current page with `place_index = nextIndex` until `hasNext` is false.
- If the first 1–2 pages have no fit, rephrase the query instead of paginating further.
- `urls.*` are safe to use directly in itinerary events — no extra lookup needed.
- Feed `id` to `get_place_info` only if you need deeper detail beyond what's returned here.
