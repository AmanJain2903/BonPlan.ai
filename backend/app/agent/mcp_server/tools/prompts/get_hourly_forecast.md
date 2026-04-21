# get_hourly_forecast

## Purpose
Retrieves the hourly weather forecast for up to 24 hours ahead for a given latitude and longitude coordinate.

## When to use
Use this tool for granular, short-term weather planning, such as finding a rain-free window for a walk later today.

## Arguments
- `lat` (float): The latitude of the location.
  - Example: `51.5074`
- `lng` (float): The longitude of the location.
  - Example: `-0.1278`
- `units_system` (Literal, optional): Distance output unit ("IMPERIAL" or "METRIC"). Default is "IMPERIAL".
  - Example: `"IMPERIAL"`
- `hours` (int, optional): The number of hours to forecast (1 to 24). Default is 24.
  - Example: `12`
- `timeout_seconds` (int, optional): Timeout in seconds. Only increase if previous call timed out. Default `10`.
  - Example: `15`

## Returns
- **Success**: A dictionary containing the `timeZone` and `forecastHours`, mapped by datetime string keys carrying `isDaytime`, `temperature`, `feelsLike`, `weatherCondition`, `precipitation`, `thunderstormProbability`, and `visibility`.
- **Error**: A dictionary containing an `error` key.
