import requests
from typing import Dict, Annotated, List, Optional
from pydantic import Field, BaseModel
import pathlib
from app.agent.mcp_server.tools.constants import WebSearchSites, SERPER_CONTENT_PARSER_PROMPT
from app.core.config import settings
from app.agent.mcp_server.caching import generate_cache_key, retrieve_api_cache, insert_api_cache
from google import genai

serper_api_key = settings.SERPER_API_KEY
gemini_api_key_serper_content_parser = settings.SERPER_CONTENT_PARSER_API_KEY
serper_content_parser_model = settings.SERPER_CONTENT_PARSER_MODEL

class ContentResponse(BaseModel):
    title: str = Field(description="The title of the content")
    content: str = Field(description="The content of the content")
    external_links: List[str] = Field(description="A list of links found in the content")

client = genai.Client(api_key=gemini_api_key_serper_content_parser)

def pre_process_content(content):
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
    try:
        response = client.models.generate_content(
                       model=serper_content_parser_model,
                       contents=f"INSTRUCTIONS: {SERPER_CONTENT_PARSER_PROMPT}\n\nCONTENT TO PROCESS:\n{content}",
                       config={
                           "response_mime_type": "application/json",
                           "response_json_schema": ContentResponse.model_json_schema(),
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
def get_content_from_url(url: Annotated[str, Field(description="The URL to get the content from.")]) -> Dict:
    cache_key = generate_cache_key("get_content", {"url": url})
    cache_value = retrieve_api_cache(cache_key, expires_in=7)
    if cache_value:
        return cache_value

    try:
        jina_url = f"https://r.jina.ai/{url}"
        headers = {
            "X-Return-Format": "markdown",
            "X-No-Layout": "true",
        }
        content = requests.get(jina_url, headers=headers)
    except Exception as e:
        return {
            "title": "Unknown Title",
            "content": "",
            "external_links": [],
            "status": f"Could not get content from {url}: {str(e)}"
        }
    if not content.ok:
        return {
            "title": "Unknown Title",
            "content": "",
            "external_links": [],
            "status": f"Could not get content from {url}: {content.status_code} {content.text}"
        }
    try:
        processed_content = pre_process_content(content.text)
        if processed_content.get("status", None) == "Success":
            insert_api_cache(cache_key, {"title": processed_content.get("title", "Unknown Title"), "content": processed_content.get("content", content.text), "external_links": processed_content.get("external_links", []), "status": processed_content.get("status", None)})
        return processed_content
    except Exception as e:
        return {
            "title": "Unknown Title",
            "content": "",
            "external_links": [],
            "status": f"Could not pre-process content from {url}: {str(e)}"
        }

# Web Search API - Serper
def search_web(query: Annotated[str, Field(description="The query to search the web for. Maximum 250 characters.")],
               site: Annotated[Optional[WebSearchSites], Field(description="The site to search the web for. If not provided, all sites will be searched.", default=None)],
               max_results: Annotated[int, Field(ge=1, le=100, description="The maximum number of results to return (min 1, max 100).", default=5)],
               search_index: Annotated[int, Field(description="The index of the result to return.", default=0)]) -> Dict:
    
    if not serper_api_key:
        return {"error": "Serper API key not configured"}

    if not query:
        return {"error": "Query is required"}
    
    # Soft test allowing minor errors in agent calculations
    if len(query) > 250 and len(query) > 350:
        return {"error": "Query is too long. Maximum 250 characters allowed."}
    
    if site:
        query = f"{query} site:{site}"
    
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
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if not response.ok:
            return {"error": f"Serper API error: {response.status_code} {response.text}", "organic_results": []}
        search_results = response.json()
        organic_results = search_results.get("organic", [])
        if not organic_results:
            return {"error": "No reliable results found for the query"}
        if len(organic_results) == 0:
            return {"error": "No reliable results found for the query"}
        
        if search_index >= len(organic_results):
            return {"error": "Search index out of range"}
        result = organic_results[search_index]
        content = get_content_from_url(result.get("link"))
        return {
            "pageTitle": content.get("title", result.get("title")),
            "pageLink": result.get("link"),
            "pageSnippet": result.get("snippet"),
            "pageContent": content.get("content", ""),
            "pageExternalLinks": content.get("external_links", []),
            "pageStatus": content.get("status", None),
            "hasNext": len(organic_results) > search_index + 1,
            "nextIndex": search_index + 1 if len(organic_results) > search_index + 1 else None,
        }

    except Exception as e:
        return {"error": f"Connection error: {str(e)}"}

PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
search_web.__doc__ = (PROMPTS_DIR / "search_web.md").read_text()
get_content_from_url.__doc__ = (PROMPTS_DIR / "get_content_from_url.md").read_text()