from app.agent.langgraph_runtime.model_hints import with_streaming_model_hints
from app.agent.llm import litellm_types as types


def test_gemini_25_flash_lite_gets_reasoning_effort_hint():
    config = with_streaming_model_hints(
        "gemini/gemini-2.5-flash-lite",
        types.GenerateContentConfig(),
    )

    assert config.extra_openai_params == {"reasoning_effort": "low"}


def test_gemini_25_flash_gets_reasoning_effort_hint():
    config = with_streaming_model_hints(
        "gemini/gemini-2.5-flash",
        types.GenerateContentConfig(),
    )

    assert config.extra_openai_params == {"reasoning_effort": "low"}


def test_non_gemini_25_model_is_unchanged():
    config = types.GenerateContentConfig()
    updated = with_streaming_model_hints("gemini/gemini-3.1-flash-lite", config)

    assert updated is config


def test_existing_extra_params_are_preserved():
    config = with_streaming_model_hints(
        "gemini/gemini-2.5-flash-lite",
        types.GenerateContentConfig(extra_openai_params={"foo": "bar"}),
    )

    assert config.extra_openai_params == {"foo": "bar", "reasoning_effort": "low"}
