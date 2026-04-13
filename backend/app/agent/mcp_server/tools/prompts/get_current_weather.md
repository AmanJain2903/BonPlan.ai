# get_current_weather

## Purpose
Retrieves the current weather conditions, temperature, visibility, and precipitation for a specific latitude and longitude coordinate using the Google Weather API.

## When to use
Use this tool when you need to know what the weather is like right now at a specific location to give recommendations or answer user queries.

## Arguments
- `lat` (float): The latitude of the location.
  - Example: `40.7128`
- `lng` (float): The longitude of the location.
  - Example: `-74.0060`
- `units_system` (Literal, optional): Distance output unit ("IMPERIAL" or "METRIC"). Default is "IMPERIAL".
  - Example: `"IMPERIAL"`

## Returns
- **Success**: A dictionary containing `isDaytime`, `weatherCondition`, `currentTemperature`, `maxTemperature`, `minTemperature`, `feelsLike`, `precipitation`, `thunderstormProbability`, and `visibility`.
- **Error**: A dictionary containing an `error` key.
