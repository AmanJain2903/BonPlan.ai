# get_place_info

## Purpose
Retrieves comprehensive details and information about a specific place using its unique Google Place ID.

## When to use
Use this tool when you already have a `place_id` (obtained from geocoding or routing) and need deeper details such as business hours, website, reviews, and specific attributes.

## Arguments
- `place_id` (str): The Google Place ID.
  - Example: `"ChIJD7fiBh9u5kcRYJSMaMOCCwQ"`

## Returns
- **Success**: A dictionary containing a `place` object with name, type, location, phone, reviews, URLs, icon, accessibility, photos, business status, hours, price level, etc.
- **Error**: A dictionary containing an `error` key.
