# get_content_from_url

## Purpose
Fetches the content of a specific URL directly and parses it into structured clean text using Jina and Gemini APIs.

## When to use
Use this tool when you have an exact URL and need to read its content. Common sources for URLs include:
- `pageExternalLinks` returned by `search_web` — follow up on relevant links found during a web search.
- `urls.websiteUrl` from place search tools (`search_places`, `search_places_nearby`, `get_place_info`) — browse a place's official website for menus, ticket prices, event schedules, etc.
- Any known URL from prior context or the user's request.

## Arguments
- `url` (str): The specific URL to retrieve.
  - Example: `"https://en.wikipedia.org/wiki/Eiffel_Tower"`
- `timeout_seconds` (int): (Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout. Default is 45 seconds.
  - Example: `60`

## Returns
- **Success**: A dictionary containing the `title`, main `content` string, `external_links` list (which you can follow by calling this tool again with any of those URLs), and processing `status`.
- **Error**: A dictionary with the `status` representing the error message and an empty `content`.
