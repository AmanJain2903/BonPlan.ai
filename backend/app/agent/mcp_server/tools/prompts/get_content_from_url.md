# get_content_from_url

## Purpose
Fetches the content of a specific URL directly and parses it into structured clean text using Jina and Gemini APIs.

## When to use
Use this tool when you have an exact link (e.g. from an earlier web search mapping or known URL) and need to read its content.

## Arguments
- `url` (str): The specific URL to retrieve.
  - Example: `"https://en.wikipedia.org/wiki/Eiffel_Tower"`

## Returns
- **Success**: A dictionary containing the `title`, main `content` string, `external_links` list, and processing `status`.
- **Error**: A dictionary with the `status` representing the error message and an empty `content`.
