# get_current_timestamp

Return the current UTC timestamp plus its ISO string. No arguments.

### When to use
- You need "now" as a reference point — e.g. sanity-check that a computed departure time is in the future, or anchor a cost calculation.

### Returns
`{ "timestamp": <int seconds>, "utc_string": "YYYY-MM-DDTHH:MM:SSZ" }`
