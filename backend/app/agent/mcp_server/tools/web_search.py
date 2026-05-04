import asyncio
from typing import Dict, Annotated, List, Optional
from pydantic import Field, BaseModel
import pathlib
from app.agent.mcp_server.tools.constants import WebSearchSites, SERPER_CONTENT_PARSER_PROMPT
from app.core.config import settings
from app.utils.http import get_http_client
from app.agent.api.caching import generate_cache_key, retrieve_api_cache, insert_api_cache
from app.agent.mcp_server.tools._errors import tool_error
from google import genai
import httpx
from app.agent.mcp_server.tools._timeouts import TIMEOUTS
from app.services.rate_limiter.rate_limiter import RateLimitExceeded, get_rate_limiter
from app.services.rate_limiter.sku_resolver import SKU, resolve_gemini_model_sku


from app.logging import get_mcp_logger
logger = get_mcp_logger("tools.web_search")
serper_api_key = settings.SERPER_API_KEY
gemini_api_key_serper_content_parser = settings.GEMINI_API_KEY
serper_content_parser_model = settings.SERPER_CONTENT_PARSER_MODEL
serper_content_parser_sku = resolve_gemini_model_sku(serper_content_parser_model)

class ContentResponse(BaseModel):
    title: str = Field(description="The title of the content")
    content: str = Field(description="The content of the content")
    external_links: List[str] = Field(description="A list of links found in the content")

client = genai.Client(api_key=gemini_api_key_serper_content_parser)

async def pre_process_content(content):
    """
    Pre-processes the content of a web page to remove unwanted elements and format the content in a readable format. 
    Using external LLM API to pre-process the content.
    It will accept the content as input and return the pre-processed content - in a JSON format with the following fields:
    - title: The title of the content
    - content: The content of the content
    - external_links: A list of links found in the content
    - status: The status of the content processing
    It will remove all other junk elements and formatting.
    """
    if not content:
        return {
            "title": "Unknown Title",
            "content": content,
            "external_links": [],
            "status": "No content provided. Check if the URL is valid and the content is accessible."
        }
    if not gemini_api_key_serper_content_parser or not serper_content_parser_model or not SERPER_CONTENT_PARSER_PROMPT:
        return {
            "title": "Unknown Title",
            "content": content,
            "external_links": [],
            "status": "Content returned without pre-processing through LLM API. Check if the API key, model or prompt is configured."
        }
        # Rate-limit gate.
    try:
        await get_rate_limiter().consume(serper_content_parser_sku, cache_hit=False)
    except RateLimitExceeded as exc:
        return {
            "title": "Unknown Title",
            "content": content,
            "external_links": [],
            "status": f"Content returned without pre-processing through LLM API, rate limit exceeded for SKU '{exc.sku}', retry after {exc.retry_after_seconds}s"
        }

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=serper_content_parser_model,
            contents=f"INSTRUCTIONS: {SERPER_CONTENT_PARSER_PROMPT}\n\nCONTENT TO PROCESS:\n{content}",
            config={
                "response_mime_type": "application/json",
                "response_json_schema": ContentResponse.model_json_schema(),
                "max_output_tokens": 512,
            },
        )
        content_response = ContentResponse.model_validate_json(response.text)
        return {
            "title": content_response.title,
            "content": content_response.content,
            "external_links": content_response.external_links,
            "status": "Success"
        }
    except Exception as e:
        return {
            "title": "Unknown Title",
            "content": content,
            "external_links": [],
            "status": f"Content returned without pre-processing through LLM API, exception in LLM API, {str(e)}"
        }

# Get content from URL using Jina and pre-process the content using Gemini API
async def get_content_from_url(url: Annotated[str, Field(description="The URL to get the content from.")],
                               timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout.", default=TIMEOUTS['get_content_from_url'])]) -> Dict:
    cache_key = await generate_cache_key("get_content", {"url": url})
    cache_value = await retrieve_api_cache(cache_key, expires_in=7)
    if cache_value:
        return cache_value

    try:
        jina_url = f"https://r.jina.ai/{url}"
        headers = {
            "X-Return-Format": "markdown",
            "X-No-Layout": "true",
        }
        http_client = get_http_client()
        content = await http_client.get(jina_url, headers=headers, timeout=timeout_seconds)
    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +15 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except Exception as e:
        return tool_error(
            f"Could not fetch content from {url}.",
            fix_hint="Verify the URL is reachable. Try a different URL (e.g. Wikipedia article on the same topic), or rely on search_web for the same information.",
            extra={"exception": str(e), "url": url},
        )
    if content.status_code >= 400:
        return tool_error(
            f"Upstream content fetch failed for {url}.",
            fix_hint="5xx responses are transient — retry once. 4xx means the page is unavailable; try a different URL (e.g. Wikipedia or official tourism site).",
            status_code=content.status_code,
            extra={"upstream": content.text[:300], "url": url},
        )
    _CONTENT_MAX_CHARS = 4000
    try:
        processed_content = await pre_process_content(content.text)
        trimmed_content = (processed_content.get("content", "") or "")[:_CONTENT_MAX_CHARS]
        result = {
            "title": processed_content.get("title", "Unknown Title"),
            "content": trimmed_content,
            "status": processed_content.get("status"),
        }
        if processed_content.get("status") == "Success":
            await insert_api_cache(cache_key, result)
        return result
    except Exception as e:
        return tool_error(
            f"Could not pre-process content from {url}.",
            fix_hint="Retry once. If it fails again, try a different source URL.",
            extra={"exception": str(e), "url": url},
        )

# Web Search API - Serper
async def search_web(query: Annotated[str, Field(description="The query to search the web for. Maximum 250 characters.")],
               site: Annotated[Optional[WebSearchSites], Field(description="(Optional) The site to search the web for. If not provided, all sites will be searched.", default=None)],
               max_results: Annotated[int, Field(ge=1, le=20, description="The maximum number of results to return (min 1, max 20).", default=5)],
               search_index: Annotated[int, Field(description="The index of the result to return.", default=0)],
               timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase if a previous call failed due to timeout.", default=TIMEOUTS['search_web'])]) -> Dict:

    if not serper_api_key:
        return tool_error(
            "Serper API key is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry. Proceed without web search.",
        )

    if not query:
        return tool_error(
            "`query` is required.",
            fix_hint="Retry with a non-empty search query.",
        )

    if len(query) > 250:
        return tool_error(
            "`query` is too long. Maximum 250 characters allowed.",
            fix_hint="Shorten the query to 250 characters or fewer. Keep the key terms and drop filler words.",
            extra={"query_length": len(query)},
        )

    if site:
        query = f"{query} site:{site}"

    # Rate-limit gate.
    try:
        await get_rate_limiter().consume(SKU["serper_web_search"], cache_hit=False)
    except RateLimitExceeded as exc:
        return tool_error(
            f"Monthly quota exhausted for SKU '{exc.sku}'.",
            fix_hint=f"Do not retry. Skip this and proceed with what you have. Retry after {exc.retry_after_seconds}s.",
            status_code=429,
            extra={"sku": exc.sku, "retry_after_seconds": exc.retry_after_seconds},
        )

    url = "https://google.serper.dev/search"
    headers = {
        'X-API-KEY': serper_api_key,
        'Content-Type': 'application/json'
    }

    payload = {
        "q": query,
        "num": max_results,
        "autocorrect": True
    }

    try:
        http_client = get_http_client()
        response = await http_client.post(url, headers=headers, json=payload, timeout=timeout_seconds)
        if response.status_code >= 400:
            return tool_error(
                "Web search failed upstream.",
                fix_hint="5xx responses are transient — retry once. 4xx usually means the query was malformed; simplify and retry.",
                status_code=response.status_code,
                extra={"upstream": response.text[:300]},
            )
        search_results = response.json()
        organic_results = search_results.get("organic", [])
        if not organic_results:
            return tool_error(
                "No reliable results found for the query.",
                fix_hint="Rephrase the query (broader terms, drop site filter if used), or try a different `site` from the allowed list.",
            )

        page_length = len(organic_results)
        if search_index >= page_length:
            return tool_error(
                f"`search_index` {search_index} is out of range.",
                fix_hint=f"This page has {page_length} result(s); choose `search_index` in [0, {page_length - 1}]. To move to the next batch, call search_web again with the same query.",
                extra={"page_length": page_length},
            )
        result = organic_results[search_index]
        content = await get_content_from_url(result.get("link"), timeout_seconds=TIMEOUTS['get_content_from_url'])
        return {
            "pageTitle": content.get("title", result.get("title")),
            "pageLink": result.get("link"),
            "pageSnippet": result.get("snippet"),
            "pageContent": content.get("content", ""),
            "pageStatus": content.get("status"),
            "hasNext": page_length > search_index + 1,
            "nextIndex": search_index + 1 if page_length > search_index + 1 else None,
        }

    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +15 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except Exception as e:
        return tool_error(
            "Web search raised an unexpected error.",
            fix_hint="Retry once with the same query. If it fails again, rephrase the query or drop the `site` filter.",
            extra={"exception": str(e)},
        )

PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
search_web.__doc__ = (PROMPTS_DIR / "search_web.md").read_text()
get_content_from_url.__doc__ = (PROMPTS_DIR / "get_content_from_url.md").read_text()
