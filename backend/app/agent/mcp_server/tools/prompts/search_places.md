# search_places

Find a real-world place (business, landmark, POI) from a free-text query.

### When to use
- You have a descriptive phrase but no coordinates or Place ID (e.g. `"pizza near Times Square"`, `"Eiffel Tower"`).
- For coordinate-centric searches prefer `search_places_nearby`.

### Arguments
- **`query`** (str, required): one subject + locality works best.
- **`include_dining_options`** (bool, optional): whether to include dining options in the response. Default false.
- **`include_amenities`** (bool, optional): whether to include amenities in the response. Default false.
- **`max_results`** (int 1..10, optional): upstream page size. Default 5.
- **`place_index`** (int, optional): which place on the page to return. Default 0.
- **`nextPageToken`** (str, optional): fetch a further page (reset `place_index` to 0).
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
One `place` + `{ nextPageToken, hasNext, nextIndex }`. Place fields: `id`, `name`, `type`, `location`, `urls{googleMapsUrl,websiteUrl}`, `reviews`, `priceLevel`, `priceRange`, `openingHours`, `accessibilityOptions`, `diningOptions`?, `amenities`?.

### Notes
- Walk the current page with `place_index = nextIndex` until `hasNext` is false.
- If the first 1–2 pages have no fit, rephrase the query instead of paginating further.
- `urls.*` are safe to use directly in itinerary events — no extra lookup needed.
- If `include_dining_options` is true, `diningOptions` will be included in the response.
- If `include_amenities` is true, `amenities` will be included in the response.
- Prefer keeping `include_dining_options` and `include_amenities` as false unless you explicitly need those fields for place selction. Keeping these fields false, you can get them if you need by calling the `get_place_info` tool with the `id`.
- Once the place is selected, feed `id` to `get_place_info` only if you need deeper detail beyond what's returned here. This will be default include as much infrmation as it can including all the optional fields from this request.
