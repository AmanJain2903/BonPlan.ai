# get_place_info

## Purpose
Retrieves comprehensive details and information about a specific place using its unique Google Place ID.

## When to use
Use this tool when you have a `place_id` from any source (geocoding, routing, or any other context) and need detailed information about that place — such as name, type, location, business hours, website, reviews, phone number, accessibility, amenities, generative summaries, and more.

## Arguments
- `place_id` (str): The Google Place ID.
  - Example: `"ChIJD7fiBh9u5kcRYJSMaMOCCwQ"`
- `timeout_seconds` (int): (Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout. Default is 15 seconds.
  - Example: `20`

## Returns
- **Success**: A dictionary containing a `place` object with: `id`, `name`, `type`, all `types`, `placeSummaries` (editorial, generative, neighborhood), `location` (address, lat, lng), `phoneNumber`, `reviews` (rating, userRatingCount, reviewSummary), `urls` (googleMapsUrl, websiteUrl), `accessibilityOptions`, `businessStatus`, `openingHours` (current, regular, secondary), `priceRange`, `priceLevel`, `parkingOptions`, `paymentOptions`, `fuelOptions`, `evChargeOptions`, and `otherOptions` (dineIn, takeout, delivery, outdoorSeating, reservable, allowsDogs, goodForChildren, goodForGroups, liveMusic, etc.).
- **Error**: A dictionary containing an `error` key.
