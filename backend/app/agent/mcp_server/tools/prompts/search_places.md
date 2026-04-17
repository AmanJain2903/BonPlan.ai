# search_places

## Purpose
Searches for real-world places (businesses, landmarks, points of interest) based on a text query using the Google Places API v1 text search. Returns a single place at the requested `place_index` with the full Google Places payload.

## When to use
Use this tool to find specific places or types of places globally based on a textual description, like `"pizza in New York"` or `"Eiffel Tower"`.

## Arguments
- `query` (str): The search string. Keep it focused — one concept plus a location works best.
  - Example: `"Spicy ramen near Times Square"`
- `max_results` (int, optional): Per-request fetch size (1 to 10). This is the page size, not a total cap across pages. Default `5`.
- `next_page_token` (str, optional): The `nextPageToken` value returned by a previous call. Supply it to fetch the next page of results for the same query.
- `place_index` (int, optional): Zero-based index into the fetched page. Valid range is `[0, len(page) - 1]`; defaults to `0`.

## Pagination semantics
One call fetches up to `max_results` places and returns the one at `place_index`. To walk the current page, re-call with `place_index = nextIndex` until `hasNext` is `false`. To fetch a further batch, re-call with the same `query` and supply `next_page_token` from the previous response (and reset `place_index = 0`).

## Returns
- **Success**: `{"place": {...}, "nextPageToken": str | null, "hasNext": bool, "nextIndex": int | null}`.
- **Error**: `{"error": str, "fix_hint": str, ...}` — follow the `fix_hint` to retry. Out-of-range `place_index` errors include `page_length` so you can pick a valid index.
