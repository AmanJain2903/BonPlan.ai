# get_daily_forecast

Daily weather forecast for up to 10 days at a lat/lng.

### When to use
- Trip-planning context: pick indoor vs outdoor activities per day, flag rain/heat-wave days, set dress-code expectations.
- Call once per destination per trip. Reuse the result across days — do NOT re-call for every event.

### Arguments
- **`lat`** / **`lng`** (float, required).
- **`days`** (int 1..10, optional): default 10. Request only what the trip spans.
- **`units_system`** (`"IMPERIAL"` | `"METRIC"`, optional): default `"IMPERIAL"`.
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
`{ timeZone, forecastDays: { "<date>": { maxTemperature, minTemperature, feelsLikeMaxTemperature, feelsLikeMinTemperature, dayTimeForecast, nightTimeForecast } } }`
