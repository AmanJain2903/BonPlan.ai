# get_coordinates

## Purpose
Converts a formal physical address or general city name into its distinct latitude and longitude geographical coordinates using the Google Geocoding API.

## When to use
Use this tool whenever a user provides a location name, and you need numerical coordinates (latitude, longitude) to use other location-based tools (like weather, places nearby, etc.).

## Arguments
- `address` (str): The address or city to geocode.
  - Example: `"1600 Amphitheatre Parkway, Mountain View, CA"` or `"Paris, France"`
- `timeout_seconds` (int): (Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout. Default is 5 seconds.
  - Example: `10`

## Returns
- **Success**: A dictionary containing `address` (the formal address), `lat`, `lng`, and `place_id`.
- **Error**: A dictionary containing an `error` key explaining the issue.
