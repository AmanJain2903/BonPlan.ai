# get_current_weather

Current weather conditions at a lat/lng.

### When to use
- You need the weather RIGHT NOW at a specific coordinate — e.g. to decide if an outdoor activity is sensible for the current event.

### Arguments
- **`lat`** / **`lng`** (float, required).
- **`units_system`** (`"IMPERIAL"` | `"METRIC"`, optional): default `"IMPERIAL"`.
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
`{ isDaytime, weatherCondition, currentTemperature, maxTemperature, minTemperature, feelsLike, precipitation, thunderstormProbability, visibility }`
