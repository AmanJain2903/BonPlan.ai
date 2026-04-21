# search_places

## Purpose
Searches for real-world places (businesses, landmarks, points of interest) based on a text query using the Google Places API v1 text search. Returns a single place at the requested `place_index` with the full Google Places payload including accessibility, amenity options, opening hours, pricing, and URLs.

## When to use
Use this tool to find specific places or types of places globally based on a textual description, like `"pizza in New York"` or `"Eiffel Tower"`.

## Arguments
- `query` (str): The search string. Keep it focused — one concept plus a location works best.
  - Example: `"Spicy ramen near Times Square"`
- `max_results` (int, optional): Per-request fetch size (1 to 10). This is the page size, not a total cap across pages. Default `5`.
- `next_page_token` (str, optional): The `nextPageToken` value returned by a previous call. Supply it to fetch the next page of results for the same query.
- `place_index` (int, optional): Zero-based index into the fetched page. Valid range is `[0, len(page) - 1]`; defaults to `0`.
- `timeout_seconds` (int): (Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout. Default is 15 seconds.
  - Example: `20`

## Pagination semantics
One call fetches up to `max_results` places and returns the one at `place_index`. To walk the current page, re-call with `place_index = nextIndex` until `hasNext` is `false`. To fetch a further batch, re-call with the same `query` and supply `next_page_token` from the previous response (and reset `place_index = 0`).

## Recommended workflow
1. Call with `max_results=5` to get a quick first result.
2. If the first result isn't ideal, iterate through more results using `place_index` (0 → 1 → 2 …) to compare options — each result includes ratings, amenities, accessibility, opening hours, and pricing.
3. To view more results beyond the current page, re-call with the returned `nextPageToken`.
4. Each result already includes `urls.googleMapsUrl` and `urls.websiteUrl`, so you can use those directly in your itinerary events without an extra tool call.

## Returns
- **Success**: `{"place": {...}, "nextPageToken": str | null, "hasNext": bool, "nextIndex": int | null}`. The `place` object contains: `id`, `name`, `type`, `placeSummary`, `location` (address, lat, lng), `urls` (googleMapsUrl, websiteUrl), `reviews` (rating, reviewSummary), `accessibilityOptions`, `businessStatus`, `openingHours` (current, regular, secondary), `priceRange`, `priceLevel`, `parkingOptions`, `paymentOptions`, `fuelOptions`, `evChargeOptions`, and `otherOptions` (dineIn, takeout, delivery, outdoorSeating, reservable, allowsDogs, goodForChildren, goodForGroups, liveMusic, etc.).
- **Error**: `{"error": str, "fix_hint": str, ...}` — follow the `fix_hint` to retry. Out-of-range `place_index` errors include `page_length` so you can pick a valid index.
