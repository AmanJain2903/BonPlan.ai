# search_places_nearby

## Purpose
Searches for real-world places within a specified radius around a latitude/longitude using the Google Places API v1 (nearby search). Returns a single place at the requested `place_index` with the full Google Places payload including accessibility, amenity options, opening hours, pricing, and URLs.

## When to use
Use this tool when you need to find specific types of places (e.g., restaurants, museums, hospitals) geographically close to a known coordinate.

## Arguments
- `lat` (float): Latitude in decimal degrees (-90 to 90). Example: `37.7749`.
- `lng` (float): Longitude in decimal degrees (-180 to 180). Example: `-122.4194`.
- `included_types` (List[str]): List of Google Places API v1 primary types to include. Must match Google's string identifiers exactly. See the list below for the most common travel-relevant values.
  - Example: `["restaurant", "cafe"]`
- `radius` (float, optional): Search radius in meters (10 to 50000). Default `500`.
- `max_results` (int, optional): Per-request fetch size (10 to 20). This is the maximum number of places Google will return in this single call — **not** a total cap across pages. Default `20`.
- `rank_preference` (Literal, optional): `"POPULARITY"` (default) or `"DISTANCE"`.
- `excluded_types` (List[str], optional): Place types to exclude. Same allowed values as `included_types`.
- `place_index` (int, optional): Zero-based index into the fetched page. Valid range is `[0, len(page) - 1]`; defaults to `0`. To iterate, re-call the tool with `place_index = nextIndex`.
- `timeout_seconds` (int): (Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout. Default is 15 seconds.
  - Example: `20`

## Pagination semantics
One call fetches up to `max_results` places from Google and returns the one at `place_index`. To walk through the page, keep calling with the same arguments but incrementing `place_index` (or using `nextIndex` from the previous response) until `hasNext` is `false`. To move past this page entirely, widen the query (larger `radius`, different `rank_preference`, or different coordinates).

## Recommended workflow
1. Call with a reasonable `radius` and `included_types` to get a first result.
2. Browse multiple results via `place_index` (0 → 1 → 2 …) to compare ratings, prices, amenities, accessibility, and proximity.
3. Each result already includes `urls.googleMapsUrl` and `urls.websiteUrl`, so you can use those directly in your itinerary events without an extra tool call.
4. Use `rank_preference = "DISTANCE"` when proximity matters most, or `"POPULARITY"` (default) for best-rated options.

## Common travel-relevant place types
```
# Dining & nightlife
restaurant, cafe, bar, bakery, coffee_shop, fine_dining_restaurant,
american_restaurant, italian_restaurant, indian_restaurant, chinese_restaurant,
japanese_restaurant, mexican_restaurant, thai_restaurant, vegetarian_restaurant,
vegan_restaurant, pizza_restaurant, seafood_restaurant, fast_food_restaurant,
ice_cream_shop, night_club, pub, brewery, wine_bar, lounge_bar

# Lodging
hotel, lodging, hostel, bed_and_breakfast, resort_hotel, motel, inn, guest_house,
campground, cottage, extended_stay_hotel

# Sights & activities
tourist_attraction, museum, art_gallery, historical_landmark, monument,
national_park, state_park, park, beach, mountain_peak, aquarium, zoo,
amusement_park, water_park, botanical_garden, observation_deck,
planetarium, performing_arts_theater

# Services & transit
airport, international_airport, subway_station, train_station, bus_station,
taxi_stand, bike_sharing_station, gas_station, parking, pharmacy, hospital,
atm, bank, tourist_information_center, visitor_center, spa

# Retail
shopping_mall, supermarket, grocery_store, market, book_store, gift_shop,
clothing_store, jewelry_store, convenience_store, pharmacy
```

If you need a type not listed above, pass the exact Google Places API v1 string identifier (snake_case, lowercase). If you guess wrong the tool returns an `error` with `invalid_included_types`, `fix_hint`, and a `valid_types_sample` — retry with a corrected list.

## Returns
- **Success**: `{"place": {...}, "hasNext": bool, "nextIndex": int | null}`. The `place` object contains: `id`, `name`, `type`, `placeSummary`, `location` (address, lat, lng), `urls` (googleMapsUrl, websiteUrl), `reviews` (rating, reviewSummary), `accessibilityOptions`, `businessStatus`, `openingHours` (current, regular, secondary), `priceRange`, `priceLevel`, `parkingOptions`, `paymentOptions`, `fuelOptions`, `evChargeOptions`, and `otherOptions` (dineIn, takeout, delivery, outdoorSeating, reservable, allowsDogs, goodForChildren, goodForGroups, liveMusic, etc.). Use `nextIndex` to paginate to the next place within the same fetch.
- **Error**: `{"error": str, "fix_hint": str, ...}`. Common shapes:
  - Invalid types → includes `invalid_included_types`, `valid_types_sample`.
  - Empty results → `fix_hint` suggests widening the radius or relaxing types.
  - Out-of-range `place_index` → includes `page_length` so you can pick a valid index.
