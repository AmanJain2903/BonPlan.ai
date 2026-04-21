# get_address

## Purpose
Converts latitude and longitude geographical coordinates into a human-readable street address using the Google Geocoding API (also known as reverse geocoding).

## When to use
Use this tool when you have coordinates and need to present a meaningful physical address to the user.

## Arguments
- `lat` (float): The latitude of the location.
  - Example: `37.4224764`
- `lng` (float): The longitude of the location.
  - Example: `-122.0842499`
- `timeout_seconds` (int): (Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout. Default is 5 seconds.
  - Example: `10`

## Returns
- **Success**: A dictionary containing `address` (the formal formatted address).
- **Error**: A dictionary containing an `error` key.
