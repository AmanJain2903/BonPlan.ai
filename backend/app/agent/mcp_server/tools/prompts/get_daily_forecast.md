# get_daily_forecast

## Purpose
Retrieves the daily weather forecast for a specified number of days (up to 10) for a given latitude and longitude coordinate.

## When to use
Use this tool to provide a multi-day forecast to aid in trip planning or weekend coordination.

## Arguments
- `lat` (float): The latitude of the location.
  - Example: `34.0522`
- `lng` (float): The longitude of the location.
  - Example: `-118.2437`
- `units_system` (Literal, optional): Distance output unit ("IMPERIAL" or "METRIC"). Default is "IMPERIAL".
  - Example: `"IMPERIAL"`
- `days` (int, optional): The number of forecast days (1 to 10). Default is 10.
  - Example: `5`

## Returns
- **Success**: A dictionary containing the target `timeZone` and `forecastDays`. Each day acts as a key for an object holding `maxTemperature`, `minTemperature`, `feelsLikeMaxTemperature`, `feelsLikeMinTemperature`, `dayTimeForecast`, and `nightTimeForecast`.
- **Error**: A dictionary containing an `error` key.
