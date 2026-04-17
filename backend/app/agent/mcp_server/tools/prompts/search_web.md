# search_web

## Purpose
Searches the web for given keywords using the Serper API. Automatically fetches and parses the primary content for the selected result using Jina and a lightweight Gemini parser.

## When to use
Use this tool whenever you need external factual knowledge or real-time web content not covered by the specific domain tools (flights, places, weather, etc.).

## Arguments
- `query` (str): The search query. Maximum 250 characters. Keep it concise — drop filler words.
  - Example: `"best museums in Paris opening hours"`
- `site` (Literal, optional): Limit to a specific trusted site. Must be one of:
  `"wikipedia.org"`, `"reddit.com"`, `"tripadvisor.com"`, `"quora.com"`, `"booking.com"`, `"expedia.com"`, `"agoda.com"`.
  Default `None` (all sites).
  - Example: `"wikipedia.org"`
- `max_results` (int, optional): Per-request fetch size (1 to 100). This is the Serper page size, not a total cap. Default `5`.
- `search_index` (int, optional): Zero-based index into the fetched organic results (valid range `[0, len(page) - 1]`). Default `0`.

## Pagination semantics
One call fetches up to `max_results` organic results and returns the full parsed content of the result at `search_index`. To walk the current page, re-call with `search_index = nextIndex` until `hasNext` is `false`. To fetch more results for the same query, re-call with the same query — Serper will reshuffle and return a fresh batch you can index into again.

## Returns
- **Success**: `{"pageTitle", "pageLink", "pageSnippet", "pageContent", "pageExternalLinks", "pageStatus", "hasNext", "nextIndex"}`.
- **Error**: `{"error", "fix_hint", ...}`. Out-of-range `search_index` errors include `page_length` so you can pick a valid index.
