# get_place_info

Full details for a specific place by Google Place ID.

### When to use
- You have a `place_id` and need more detail than `search_places` already returned (phone number, parking, EV charging, secondary hours, generative summaries).
- Don't call this just to re-fetch fields `search_places` already gave you.

### Arguments
- **`place_id`** (str, required).
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
`{ place: { id, name, type, types, placeSummaries{editorial,generative,neighborhood}, location, phoneNumber, reviews, urls, accessibilityOptions, businessStatus, openingHours, priceRange, priceLevel, parkingOptions, paymentOptions, fuelOptions, evChargeOptions, otherOptions } }`
