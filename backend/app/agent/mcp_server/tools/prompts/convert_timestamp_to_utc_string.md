# convert_timestamp_to_utc_string

Convert a Unix timestamp (seconds) to an ISO 8601 UTC string.

### When to use
- A tool returned an epoch integer and you need it as a readable string for an itinerary field or downstream call.

### Arguments
- **`timestamp`** (int, required): Unix seconds. Must be seconds, NOT milliseconds — divide by 1000 if the source is JS-style.

### Returns
`{ "utc_string": "YYYY-MM-DDTHH:MM:SSZ" }`
