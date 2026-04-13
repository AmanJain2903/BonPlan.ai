# convert_utc_string_to_timestamp

## Purpose
Converts a strict ISO 8601 UTC time string into an absolute Unix timestamp (in seconds).

## When to use
Use this tool to convert human-readable UTC dates into a numerical UNIX epoch format required by certain APIs or mathematical logic.

## Arguments
- `utc_string` (str): Strict ISO 8601 UTC time string. Must end with 'Z' or valid UTC offset.
  - Example: `"2026-04-05T18:30:00Z"`

## Returns
- **Success**: A dictionary containing `timestamp` (an integer).
- **Error**: A dictionary containing an `error` key.
