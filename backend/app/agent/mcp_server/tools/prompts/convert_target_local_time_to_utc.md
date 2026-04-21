# convert_target_local_time_to_utc

## Purpose
Converts a valid local "wall-clock" time at a specific timezone into its absolute UTC counterpart (both string and epoch timestamp).

## When to use
Use this tool whenever a user asks to schedule an event in their local time zone, and you need to supply UTC timings strictly formatted for internal calculations or other apis.

## Arguments
- `local_time_string` (str): Local formatted time (without trailing 'Z').
  - Example: `"2026-04-25T20:00:00"`
- `timezone_id` (str): Valid IANA Timezone ID.
  - Example: `"Europe/Paris"`

## Returns
- **Success**: A dictionary containing `original_local_time`, `utc_string`, and `utc_timestamp`.
- **Error**: A dictionary containing an `error` key.
