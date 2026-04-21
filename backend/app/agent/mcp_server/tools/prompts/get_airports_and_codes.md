# get_airports_and_codes

## Purpose
Retrieves a list of airports and their IATA airport codes based on a search query (such as a city or airport name) using Google Flights API (via RapidAPI).

## When to use
Use this as a prerequisite step when planning a trip or flight to find the correct `airport_code` based on a location name provided by the user.

## Arguments
- `query` (str): The query to search airports for.
  - Example: `"Los Angeles"`
- `country_code` (str, optional): The country code to filter the results.
  - Example: `"US"`
- `timeout_seconds` (int): (Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout. Default is 10 seconds.
  - Example: `15`

## Returns
- **Success**: A dictionary mapping airport/place titles to another dictionary containing `airport_code` and `distance`.
  - Example: `{"Los Angeles International Airport": {"airport_code": "LAX", "distance": None}}`
- **Error**: A dictionary containing an `error` key if no airports are found or a connection issue occurs.
