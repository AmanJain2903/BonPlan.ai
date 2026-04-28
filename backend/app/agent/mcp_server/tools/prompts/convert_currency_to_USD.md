# convert_currency_to_USD

Converts an amount from a target currency into USD using latest exchange rates.

### When to use
- A price/fare is provided in a non-USD currency and you need normalized USD cost for outputing events.
- Budget comparison and events requires all prices and costs in USD.

### Arguments
- **`to_currency`** (str, required): 3-letter currency code to convert from (example: `EUR`, `GBP`, `INR`).
- **`amount`** (float, required): amount in `to_currency`.
- **`timeout_seconds`** (int, optional): only increase after a prior timeout.

### Returns
`{ convertedAmountInUSD }`

### Notes
- Use `get_supported_currencies` or `search_web` first if the currency code is unknown or uncertain.
- For deterministic budgeting, use the returned `convertedAmountInUSD` value.
