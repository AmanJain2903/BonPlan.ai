# get_country_code

## Purpose
Retrieves the corresponding country code for a given country name using Google Flights API data (via RapidAPI).

## When to use
Use this tool when you have a country's name but need its standard ISO 3166-1 alpha-2 or similar code to pass to other flight or location-based tools. 

## Arguments
- `country_name` (str): The name of the country. Just the country name, with no additional text.
  - Example: `"France"`
- `timeout_seconds` (int): (Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout. Default is 5 seconds.
  - Example: `10`

## Returns
- **Success**: A dictionary containing `country_code` (e.g., "FR" for France).
- **Error**: A dictionary containing an `error` key explaining the issue.
