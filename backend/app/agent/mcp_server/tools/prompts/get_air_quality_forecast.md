# get_air_quality_forecast

## Purpose
Gets the forecasted air quality index (AQI), category, and health recommendations for a specific location up to 96 hours into the future using the Google Air Quality API.

## When to use
Use this tool to provide future air quality predictions for outdoor planning. Note that it supports point in time up to 96 hours ahead from the current time.

## Arguments
- `lat` (float): The precise latitude of the location.
  - Example: `34.0522`
- `lng` (float): The precise longitude of the location.
  - Example: `-118.2437`
- `point_in_time` (str, optional): The specific UTC datetime to forecast in ISO 8601 format. If omitted, defaults to 1 hour from current UTC time.
  - Example: `"2026-04-15T18:00:00Z"`
- `timeout_seconds` (int, optional): Timeout in seconds for the tool execution. Only increase this if a previous call failed due to timeout. Default is `10`.
  - Example: `10`

## Returns
- **Success**: A dictionary containing:
  - `dateTime`: The exact time of the forecast
  - `aqi`: Forested AQI
  - `color`: Color code
  - `category`: Category name
  - `health_recommendations`: Relevant health recommendations
- **Error**: A dictionary containing an `error` key explaining the cause of failure.
