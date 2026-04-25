# search_places_nearby

Find places of specific categories within a radius of a known coordinate.

### When to use
- You already have a lat/lng anchor (hotel, stop, landmark) and want things nearby.
- For free-text discovery without coordinates, use `search_places`.

### Arguments
- **`lat`** / **`lng`** (float, required).
- **`included_types`** (list[str], required): Google Places API v1 primary types (snake_case, e.g. `restaurant`, `museum`, `tourist_attraction`, `subway_station`). Invalid entries return a `valid_types_sample`.
- **`excluded_types`** (list[str], optional).
- **`radius`** (int meters, 10..50000, optional): default 1500. Start tight, widen only if needed.
- **`include_dining_options`** (bool, optional): whether to include dining options in the response. Default false.
- **`include_amenities`** (bool, optional): whether to include amenities in the response. Default false.
- **`max_results`** (int 10..20, optional): single page — no token.
- **`rank_preference`** (`"POPULARITY"` | `"DISTANCE"`, optional).
- **`place_index`** (int, optional): which place on the page. Default 0.
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
One `place` + `{ hasNext, nextIndex }`. Same place shape as `search_places`.

### Notes
- Walk the page with `place_index = nextIndex`.
- Zero results → widen radius, relax `included_types`, or drop `excluded_types`.
- Common types: dining (`restaurant`, `cafe`, `bar`, `bakery`, `*_restaurant`), lodging (`hotel`, `hostel`), sights (`tourist_attraction`, `museum`, `park`, `beach`), transit (`subway_station`, `train_station`, `airport`), retail (`shopping_mall`, `market`).
- If `include_dining_options` is true, `diningOptions` will be included in the response.
- If `include_amenities` is true, `amenities` will be included in the response.
- Prefer keeping `include_dining_options` and `include_amenities` as false unless you explicitly need those fields for place selction. Keeping these fields false, you can get them if you need by calling the `get_place_info` tool with the `id`.
- Once the place is selected, feed `id` to `get_place_info` only if you need deeper detail beyond what's returned here. This will be default include as much infrmation as it can including all the optional fields from this request.
