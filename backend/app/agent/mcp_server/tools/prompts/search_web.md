# search_web

Web search (Serper) + automatic full-page parse of one selected result.

### When to use
- You need external facts not covered by the domain tools (places, flights, weather, routing).
- Good for: neighborhood vibes, event calendars, opening hours cross-checks, travel advisories.

### Arguments
- **`query`** (str ≤ 250 chars, required): concise — drop filler words.
- **`site`** (optional): restrict to one of `wikipedia.org`, `reddit.com`, `tripadvisor.com`, `quora.com`, `booking.com`, `expedia.com`, `agoda.com`.
- **`max_results`** (int 1..20, optional): page size. Default 5.
- **`search_index`** (int, optional): which result on the page to fully parse. Default 0.
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
`{ pageTitle, pageLink, pageSnippet, pageContent, pageExternalLinks, pageStatus, hasNext, nextIndex }`

### Notes
- To read a different result on the same page, re-call with the next `search_index` (walk until `hasNext` is false).
- To dive into a specific URL (e.g. an `externalLink` or a place's `websiteUrl`), use `get_content_from_url`.
- To change angle, change the query — don't just paginate.
