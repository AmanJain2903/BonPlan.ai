# get_content_from_url

Fetch a specific URL and return structured, cleaned text (Jina + Gemini parser).

### When to use
- You have a concrete URL worth reading: a place's `websiteUrl`, a `pageExternalLinks` entry from `search_web`, or a link the user provided.
- Skip if the question can be answered from a snippet — don't pull full pages speculatively.

### Arguments
- **`url`** (str, required).
- **`timeout_seconds`** (int, optional): Only raise after a prior timeout.

### Returns
`{ title, content, external_links, status }`
