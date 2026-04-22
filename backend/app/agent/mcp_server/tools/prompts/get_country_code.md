# get_country_code

ISO country code for a country name (needed by some flight/search tools).

### When to use
- Preparing arguments for flight tools that require a country code and you only have the country name.

### Arguments
- **`country_name`** (str, required): just the country name.
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
`{ country_code: str }` (e.g. `"FR"`).
