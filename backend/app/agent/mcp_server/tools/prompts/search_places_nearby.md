# search_places_nearby

## Purpose
Searches for real-world places within a specified radius around a specific latitude and longitude coordinate using the Google Places API.

## When to use
Use this tool when you need to find specific types of places (e.g., restaurants, museums, hospitals) geographically close to a known coordinate.

## Arguments
- `lat` (float): The latitude of the location.
  - Example: `37.7749`
- `lng` (float): The longitude of the location.
  - Example: `-122.4194`
- `included_types` (List[str]): List of valid `GooglePlaceType` literal strings to search for (e.g., `"restaurant"`, `"hospital"`, etc.). You can pass multiple types to widen the search.
  - Example: `["restaurant", "cafe"]`
- `radius` (float, optional): The search radius in meters (10 to 50000). Default is 500.
  - Example: `1000`
- `max_results` (int, optional): Max results (10 to 20). Default is 20.
  - Example: `15`
- `rank_preference` (Literal, optional): "POPULARITY" or "DISTANCE". Default is "POPULARITY".
  - Example: `"DISTANCE"`
- `excluded_types` (List[str], optional): Place types to exclude.
  - Example: `["fast_food_restaurant"]`
- `place_index` (int, optional): The index of the specific place in the list to return details for. Default is 0.
  - Example: `0`

## Returns
- **Success**: A dictionary containing the target `place` details and pagination helpers (`hasNext`, `nextIndex`). If `hasNext` is true, you can perform the exact same tool call but with `place_index` set to `nextIndex` to retrieve the details of the next place in the list.
- **Error**: A dictionary containing an `error` key.
