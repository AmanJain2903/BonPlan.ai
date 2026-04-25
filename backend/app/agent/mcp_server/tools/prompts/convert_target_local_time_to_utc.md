# convert_target_local_time_to_utc

Convert a local wall-clock time at a specific IANA timezone to its UTC counterpart (both ISO string and epoch seconds).

### When to use
- The user wants an event at a specific local time (e.g. "dinner at 8 PM Paris time") and you need the equivalent UTC for scheduling or API calls.
- Crossing timezones: convert the destination's local time to UTC before comparing against origin-local times.

### Arguments
- **`local_time_string`** (str, required): Naive local time `YYYY-MM-DDTHH:MM:SS` — NO trailing `Z` or offset.
- **`timezone_id`** (str, required): IANA zone such as `"Europe/Paris"` or `"Asia/Kolkata"`. If unknown, resolve via `get_timezone` first.

### Returns
`{ "original_local_time": ..., "utc_string": ..., "utc_timestamp": <int> }`
