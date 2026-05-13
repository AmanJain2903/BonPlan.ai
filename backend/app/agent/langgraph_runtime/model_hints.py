"""App-level model-specific request hints for streamed chat."""

from __future__ import annotations

from dataclasses import replace

from app.agent.llm import litellm_types as types


def _is_reasoning_gemini_25(model: str) -> bool:
    provider, _, model_name = (model or "").partition("/")
    provider = provider.strip().lower()
    model_name = model_name.strip().lower()
    return provider == "gemini" and model_name in {
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    }


def with_streaming_model_hints(
    model: str,
    config: types.GenerateContentConfig,
) -> types.GenerateContentConfig:
    """Attach provider params needed for models with known streaming quirks."""
    if not _is_reasoning_gemini_25(model):
        return config

    extra = dict(config.extra_openai_params or {})
    extra.setdefault("reasoning_effort", "low")
    return replace(config, extra_openai_params=extra)
