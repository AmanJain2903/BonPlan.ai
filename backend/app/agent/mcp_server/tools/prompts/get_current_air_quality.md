# get_current_air_quality

## Purpose
Gets the current air quality index (AQI), color category, and health recommendations for a specific location using the Google Air Quality API.

## When to use
Use this tool when the user asks for the current air quality at a specific place. It provides real-time AQI and advice for different health conditions (e.g., allergies).

## Arguments
- `lat` (float): The precise latitude of the location.
  - Example: `37.7749`
- `lng` (float): The precise longitude of the location.
  - Example: `-122.4194`
- `timeout_seconds` (int, optional): Timeout in seconds for the tool execution. Only increase this if a previous call failed due to timeout. Default is `5`.
  - Example: `10`

## Returns
- **Success**: A dictionary containing:
  - `aqi`: The Air Quality Index (e.g., 45)
  - `color`: The color code corresponding to the category (e.g., "green")
  - `category`: The category name (e.g., "Good")
  - `health_recommendations`: General health advice based on currently calculated AQI.
- **Error**: A dictionary containing an `error` key explaining the cause of failure.
