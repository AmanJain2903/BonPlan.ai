# search_places

## Purpose
Searches for real-world places (businesses, landmarks, points of interest) based on a text query string using the Google Places API.

## When to use
Use this tool to find specific places or types of places globally based on a textual description, like "pizza in New York" or "Eiffel Tower".

## Arguments
- `query` (str): The query string.
  - Example: `"Spicy food near Times Square"`
- `max_results` (int, optional): Max results to return (1 to 10). Default is 5.
  - Example: `5`
- `next_page_token` (str, optional): Pagination token for viewing more results.
  - Example: `"A_VALiD_TOkEn"`
- `place_index` (int, optional): The index of the specific place in the list to return details for. Default is 0.
  - Example: `0`

## Returns
- **Success**: A dictionary containing detailed `place` information (name, type, summaries, location, reviews, website, hours, options), `nextPageToken`, and pagination helpers (`hasNext`, `nextIndex`). If `hasNext` is true, you can perform the exact same call with `place_index` set to `nextIndex` to retrieve the next place. If `nextIndex` is out of bounds, you can supply the `nextPageToken` (if available) with `place_index` = 0 to fetch the next block of places.
- **Error**: A dictionary containing an `error` key.
