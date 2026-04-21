# get_timezone

## Purpose
Retrieves the timezone name, unique ID, daylight saving data, and local time for a specific latitude and longitude coordinate.

## When to use
Use this tool when you know the coordinates of a location and need to determine its IANA timezone ID to properly calculate time-based events.

## Arguments
- `lat` (float): The latitude of the location.
  - Example: `48.8566`
- `lng` (float): The longitude of the location.
  - Example: `2.3522`
- `timestamp` (int, optional): An epoch time in seconds. If omitted, uses current time and skips returning offset details.
  - Example: `1700000000`
- `timeout_seconds` (int): (Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout. Default is 10 seconds.
  - Example: `15`

## Returns
- **Success**: A dictionary containing `timeZoneId`, `timeZoneName`, and (optionally) `dstOffset`, `rawOffset`, and `localDateTimeString`.
- **Error**: A dictionary containing an `error` key.
