# get_airports_and_codes

Airports + IATA codes for a city/area query.

### When to use
- Resolving a user-supplied city to actual airport codes before calling flight tools.

### Arguments
- **`query`** (str, required): city or airport name.
- **`country_code`** (str, optional): filter by ISO country code (pair with `get_country_code` if only a country name is known).
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
`{ "<Airport title>": { airport_code, distance } }`
