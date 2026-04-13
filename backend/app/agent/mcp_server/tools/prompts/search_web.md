# search_web

## Purpose
Searches the web for given keywords using Serper API. Automatically fetches and parses the primary content for the selected search result link using Jina and Gemini API.

## When to use
Use this tool whenever you need external factual knowledge or to perform real-time searches not covered by specific internal tools. 

## Arguments
- `query` (str): The search query (max 250 characters).
  - Example: `"best museums in Paris"`
- `site` (Literal, optional): Limits the search to specific predefined top-level domains/sites if needed. Default is None.
  - Example: `"WIKIPEDIA"`
- `max_results` (int, optional): Max results to retrieve (min 1, max 100). Default is 5.
  - Example: `10`
- `search_index` (int, optional): The index of the specific result to return the full parsed content from. Default is 0.
  - Example: `0`

## Returns
- **Success**: A dictionary containing `pageTitle`, `pageLink`, `pageSnippet`, full `pageContent`, `pageExternalLinks`, and `pageStatus`, along with pagination flags `hasNext` and `nextIndex`. If `hasNext` is true, you can make the exact same call with `search_index` set to the `nextIndex` to fetch the next sequential organic result from the list.
- **Error**: A dictionary containing an `error` key.
