from typing import Dict, Annotated, Optional
from pydantic import Field
from app.core.config import settings
from app.utils.http import get_http_client
from app.agent.mcp_server.tools._errors import tool_error
from datetime import datetime, timezone, timedelta
import pathlib
import httpx
from app.agent.mcp_server.tools._timeouts import TIMEOUTS
from app.services.rate_limiter.rate_limiter import RateLimitExceeded, get_rate_limiter
from app.services.rate_limiter.sku_resolver import SKU
from app.agent.api.caching import generate_cache_key, retrieve_api_cache, insert_api_cache


from app.logging import get_mcp_logger
logger = get_mcp_logger("tools.currency")
async def _currency_consume_or_error() -> Optional[Dict]:
    try:
        await get_rate_limiter().consume(SKU["exchange_rates"])
        return None
    except RateLimitExceeded as exc:
        return tool_error(
            "Monthly Exchange Rates SKU quota exhausted.",
            fix_hint=f"Do not retry. Skip currency conversion. Retry after {exc.retry_after_seconds}s.",
            status_code=429,
            extra={"sku": exc.sku, "retry_after_seconds": exc.retry_after_seconds},
        )

rapid_api_key = settings.RAPID_API_KEY


# Exchange Rates API
async def get_supported_currencies(timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase this if a previous call failed due to timeout.", default=TIMEOUTS['get_supported_currencies'])]) -> Dict:
    if not rapid_api_key:
        return tool_error(
            "Rapid API key is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry.",
        )
    
    cache_key = await generate_cache_key("get_supported_currencies", {"type": "all_codes"})
    cache_value = await retrieve_api_cache(cache_key, expires_in=31)
    if cache_value:
        return {
            "currencyCodes": cache_value.get("supported_codes", [])
        }
    
    rl_error = await _currency_consume_or_error()
    if rl_error:
        return rl_error

    url = "https://exchange-rates7.p.rapidapi.com/codes"
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": "exchange-rates7.p.rapidapi.com",
        "x-rapidapi-key": rapid_api_key
    }
    try:
        response = await get_http_client().get(url, headers=headers)
        if response.status_code != 200:
            return tool_error(
                "Failed to get supported currencies.",
                fix_hint="Retry once with the same arguments. If it fails again, proceed without currency data.",
                status_code=response.status_code,
                extra={"upstream": response.text[:300]},
            )
        data = response.json()
        if data and data.get("supported_codes", []):
            await insert_api_cache(cache_key, data)
        return {
            "currencyCodes": data.get("supported_codes", [])
        }
    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +5 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except Exception as e:
        return tool_error(
            "Failed to get supported currencies.",
            fix_hint="Retry once with the same arguments. If it fails again, proceed without currency data.",
            extra={"exception": str(e)},
        )

async def convert_currency_to_USD(to_currency: Annotated[str, Field(description="The currency code to convert to example: EUR, GBP, INR, etc. If unsure, use the `get_supported_currencies` or `search_web` tool to get the list of supported currencies and their codes.")],
                                  amount: Annotated[float, Field(description="The amount to convert to USD.")],
                                  timeout_seconds: Annotated[Optional[int], Field(description="(Optional) Timeout in seconds for the tool execution. Only increase this if a previous call failed due to timeout.", default=TIMEOUTS['convert_currency_to_USD'])]) -> Dict:
    if not rapid_api_key:
        return tool_error(
            "Rapid API key is not configured on the server.",
            fix_hint="This is a server-side configuration issue — do not retry.",
        )

    rl_error = await _currency_consume_or_error()
    if rl_error:
        return rl_error
    
    url = "https://exchange-rates7.p.rapidapi.com/latest?base=USD"
    headers = {
        "Content-Type": "application/json",
        "x-rapidapi-host": "exchange-rates7.p.rapidapi.com",
        "x-rapidapi-key": rapid_api_key
    }
    try:
        response = await get_http_client().get(url, headers=headers)
        if response.status_code != 200:
            return tool_error(
                "Failed to convert currency to USD.",
                fix_hint="Retry once with the same arguments. If it fails again, proceed without currency data.",
                status_code=response.status_code,
                extra={"upstream": response.text[:300]},
            )
        data = response.json()
        if data and data.get("rates", {}):
            exchange_rate = data.get("rates", {}).get(to_currency.upper(), 0)
            price_in_usd = amount / exchange_rate
            return {
                "convertedAmountInUSD": round(price_in_usd, 2),
            }
        else:
            return tool_error(
                "Failed to convert currency to USD.",
                fix_hint="Retry once with the same arguments. If it fails again, proceed without currency data.",
                extra={"upstream": response.text[:300]},
            )
    except httpx.TimeoutException:
        return tool_error(
            f"Tool timeout after {timeout_seconds} seconds.",
            fix_hint="Try calling this tool exactly ONCE more with a slightly greater timeout_seconds parameter (e.g. +5 seconds). If it fails again, skip calling it and gracefully continue."
        )
    except Exception as e:
        return tool_error(
            "Failed to convert currency to USD.",
            fix_hint="Retry once with the same arguments. If it fails again, proceed without currency data.",
            extra={"exception": str(e)},
        )
    
    

PROMPTS_DIR = pathlib.Path(__file__).parent / "prompts"
get_supported_currencies.__doc__ = (PROMPTS_DIR / "get_supported_currencies.md").read_text()
convert_currency_to_USD.__doc__ = (PROMPTS_DIR / "convert_currency_to_USD.md").read_text()