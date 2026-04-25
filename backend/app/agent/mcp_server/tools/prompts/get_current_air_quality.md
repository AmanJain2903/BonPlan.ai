# get_current_air_quality

Current AQI + category + health advice at a lat/lng.

### When to use
- An outdoor activity or a user with respiratory/allergy concerns needs a go/no-go check right now.
- Skip for indoor events.

### Arguments
- **`lat`** / **`lng`** (float, required).
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
`{ aqi: int, color: str, category: str, health_recommendations: { ... } }`
