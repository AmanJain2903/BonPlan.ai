# get_current_timestamp

## Purpose
Gets the current absolute Unix timestamp in seconds along with the corresponding UTC ISO string.

## When to use
Use this tool whenever you need the exact present time, whether to validate future inputs, to calculate offsets, or to supply a current timestamp to other chronological APIs.

## Arguments
This tool takes no arguments.

## Returns
- **Success**: A dictionary containing `timestamp` (e.g., `1712953200`) and `utc_string` (e.g., `'2024-04-12T20:20:00Z'`).
- **Error**: A dictionary containing an `error` key.
