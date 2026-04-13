# convert_timestamp_to_utc_string

## Purpose
Converts a Unix timestamp (in seconds) into a readable ISO 8601 UTC string.

## When to use
Use this tool when you need to convert an epoch integer timestamp returned by a tool into a standard formatted ISO timeline string.

## Arguments
- `timestamp` (int): Absolute Unix timestamp in seconds.
  - Example: `1806949800`

## Returns
- **Success**: A dictionary containing `utc_string`.
- **Error**: A dictionary containing an `error` key.
