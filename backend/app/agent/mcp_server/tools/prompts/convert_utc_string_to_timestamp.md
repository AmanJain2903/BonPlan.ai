# convert_utc_string_to_timestamp

Convert an ISO 8601 UTC time string to a Unix timestamp (seconds).

### When to use
- An upstream tool demands an epoch integer but you only have a human-readable UTC string.

### Arguments
- **`utc_string`** (str, required): ISO 8601 ending in `Z` or a valid UTC offset. Example: `"2026-04-05T18:30:00Z"`.

### Returns
`{ "timestamp": <int seconds> }`
