# get_air_quality_forecast

Forecasted AQI + category + health advice for a specific future hour at a lat/lng (up to 96 h ahead).

### When to use
- Outdoor event planned for a specific day/hour and air quality is a concern (respiratory, allergy, wildfire season).
- Skip when `get_current_air_quality` or `get_daily_forecast` already answered the question.

### Arguments
- **`lat`** / **`lng`** (float, required).
- **`point_in_time`** (str ISO 8601 UTC, optional): target hour. Defaults to now + 1 h.
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
`{ dateTime, aqi, color, category, health_recommendations }`
