# get_hourly_forecast

Hour-by-hour weather forecast for the next 1–24 hours at a lat/lng.

### When to use
- Short-horizon planning within today: finding a dry window for a walk, deciding whether to shift an outdoor event by a few hours.
- Do NOT use for trip-wide planning — prefer `get_daily_forecast` for that.

### Arguments
- **`lat`** / **`lng`** (float, required).
- **`hours`** (int 1..24, optional): default 24. Request only what you actually need.
- **`units_system`** (`"IMPERIAL"` | `"METRIC"`, optional): default `"IMPERIAL"`.
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
`{ timeZone, forecastHours: { "<datetime>": { isDaytime, temperature, feelsLike, weatherCondition, precipitation, thunderstormProbability, visibility } } }`
