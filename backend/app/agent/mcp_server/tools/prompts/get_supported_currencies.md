# get_supported_currencies

Returns the full list of supported currency codes from the exchange-rate provider.

### When to use
- You need valid currency codes before running a conversion.
- You need to verify whether a code (e.g. `EUR`, `INR`) is supported.

### Arguments
- **`timeout_seconds`** (int, optional): only increase after a prior timeout.

### Returns
`{ currencyCodes }`

### Notes
- This is code discovery only; it does not return conversion rates or converted amounts.
- If conversion is still needed, call `convert_currency_to_USD` with one code from `currencyCodes`.
