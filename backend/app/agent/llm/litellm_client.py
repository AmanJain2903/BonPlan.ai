"""LiteLLM-backed chat client used by the agent runtime."""

from __future__ import annotations

import json
import os
import uuid
from inspect import isawaitable
from typing import Any, Iterable, Optional

from app.core.config import settings

import litellm
from litellm import acompletion, completion, token_counter

from app.logging import get_agent_logger

from . import litellm_types as types

log = get_agent_logger("litellm_client")


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False)


def _json_loads(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _normalize_finish_reason(reason: Any) -> str:
    raw = str(reason or "").strip()
    lower = raw.lower()
    if lower in {"length", "max_tokens", "max_output_tokens"}:
        return "MAX_TOKENS"
    if lower in {"tool_calls", "function_call"}:
        return "TOOL_CALLS"
    if lower == "stop":
        return "STOP"
    return raw.upper() if raw else ""


def configure_litellm() -> None:
    """Expose configured provider keys under the env names LiteLLM expects."""
    provider_env = {
        "OPENROUTER_API_KEY": settings.OPENROUTER_API_KEY,
        "LITELLM_LOCAL_MODEL_COST_MAP": "True",
    }
    for key, value in provider_env.items():
        if value and not os.getenv(key):
            os.environ[key] = value

    litellm.drop_params = True
    litellm.set_verbose = False
    # Prevent repeated provider-list debug noise in terminal output.
    if hasattr(litellm, "suppress_debug_info"):
        litellm.suppress_debug_info = True


def _tool_blocks_to_openai_tools(
    tool_blocks: Optional[Iterable[types.Tool]],
) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for block in tool_blocks or []:
        if block is None:
            continue
        tools.extend(block.to_openai_tools())
    return tools


def _config_to_completion_kwargs(
    config: Optional[types.GenerateContentConfig],
) -> dict[str, Any]:
    if config is None:
        return {}
    kwargs: dict[str, Any] = {}
    if config.temperature is not None:
        kwargs["temperature"] = config.temperature
    if config.max_output_tokens is not None:
        kwargs["max_tokens"] = config.max_output_tokens
    tools = _tool_blocks_to_openai_tools(config.tools)
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    if config.response_format is not None:
        kwargs["response_format"] = config.response_format
    elif config.response_json_schema:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "response_schema",
                "schema": config.response_json_schema,
            },
        }
    elif config.response_mime_type == "application/json":
        kwargs["response_format"] = {"type": "json_object"}
    return kwargs


def _content_to_messages(content: types.Content) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    text_parts: list[str] = []
    for part in content.parts or []:
        if part.text:
            text_parts.append(part.text)
        if part.function_response:
            messages.append(_function_response_to_message(part.function_response))
    if text_parts:
        role = content.role if content.role in {"system", "user", "assistant"} else "user"
        messages.insert(0, {"role": role, "content": "\n".join(text_parts)})
    return messages


def _function_response_to_message(
    function_response: types.FunctionResponse,
) -> dict[str, Any]:
    tool_call_id = function_response.tool_call_id or f"call_{uuid.uuid4().hex}"
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "name": function_response.name,
        "content": _json_dumps(function_response.response),
    }


def _input_to_messages(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, str):
        return [{"role": "user", "content": value}]
    if isinstance(value, types.Content):
        return _content_to_messages(value)
    if isinstance(value, dict):
        return [dict(value)]
    if isinstance(value, list):
        if all(isinstance(item, dict) for item in value):
            return [dict(item) for item in value]
        messages: list[dict[str, Any]] = []
        text_parts: list[str] = []
        for item in value:
            if isinstance(item, types.Part):
                if item.text:
                    text_parts.append(item.text)
                if item.function_response:
                    messages.append(_function_response_to_message(item.function_response))
            elif isinstance(item, str):
                text_parts.append(item)
        if text_parts:
            messages.insert(0, {"role": "user", "content": "\n".join(text_parts)})
        return messages
    return [{"role": "user", "content": str(value)}]


def _normalize_history(history: Optional[list[Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in history or []:
        normalized.extend(_input_to_messages(item))
    return normalized


def _message_content_from_contents(contents: Any) -> str:
    if isinstance(contents, list):
        return "\n".join(str(item) for item in contents)
    return str(contents)


def _extract_response_text(resp: Any) -> str:
    try:
        message = _get(_get(resp, "choices", [])[0], "message")
        content = _get(message, "content", "")
        return content or ""
    except Exception:
        return ""


def _serialize_tool_call(tool_call: Any) -> dict[str, Any]:
    fn = _get(tool_call, "function", {}) or {}
    args = _get(fn, "arguments", "")
    if not isinstance(args, str):
        args = _json_dumps(args)
    return {
        "id": _get(tool_call, "id") or f"call_{uuid.uuid4().hex}",
        "type": _get(tool_call, "type", "function") or "function",
        "function": {
            "name": _get(fn, "name", ""),
            "arguments": args,
        },
    }


def _stream_tool_call_to_function_call(data: dict[str, Any]) -> types.FunctionCall:
    fn = data.get("function") or {}
    return types.FunctionCall(
        id=data.get("id") or f"call_{uuid.uuid4().hex}",
        name=str(fn.get("name") or ""),
        args=_json_loads(fn.get("arguments") or "{}"),
    )


async def _maybe_await(value: Any) -> Any:
    if isawaitable(value):
        return await value
    return value


class LiteLLMModels:
    async def generate_content(
        self,
        *,
        model: str,
        contents: Any,
        config: Optional[types.GenerateContentConfig] = None,
    ) -> Any:
        messages = _input_to_messages(_message_content_from_contents(contents))
        if config and config.system_instruction:
            messages.insert(0, {"role": "system", "content": config.system_instruction})
        resp = await _maybe_await(
            acompletion(
                model=model,
                messages=messages,
                **_config_to_completion_kwargs(config),
            )
        )
        return type("LiteLLMTextResponse", (), {"text": _extract_response_text(resp)})()

    async def count_tokens(
        self,
        *,
        model: str,
        contents: Any,
        config: Optional[types.GenerateContentConfig] = None,
    ) -> Any:
        messages = _normalize_history(contents if isinstance(contents, list) else [contents])
        if config and config.system_instruction:
            messages.insert(0, {"role": "system", "content": config.system_instruction})
        kwargs = _config_to_completion_kwargs(config)
        total = token_counter(
            model=model,
            messages=messages,
            tools=kwargs.get("tools"),
        )
        return type("LiteLLMTokenCount", (), {"total_tokens": int(total or 0)})()


class LiteLLMSyncModels:
    def generate_content(
        self,
        *,
        model: str,
        contents: Any,
        config: Optional[types.GenerateContentConfig] = None,
    ) -> Any:
        messages = _input_to_messages(_message_content_from_contents(contents))
        if config and config.system_instruction:
            messages.insert(0, {"role": "system", "content": config.system_instruction})
        resp = completion(
            model=model,
            messages=messages,
            **_config_to_completion_kwargs(config),
        )
        return type("LiteLLMTextResponse", (), {"text": _extract_response_text(resp)})()


class LiteLLMChatSession:
    def __init__(
        self,
        *,
        model: str,
        config: Optional[types.GenerateContentConfig] = None,
        history: Optional[list[Any]] = None,
    ) -> None:
        self.model = model
        self.config = config
        self._history = _normalize_history(history)

    def get_history(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._history]

    def _messages_for_request(self, input_messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        if self.config and self.config.system_instruction:
            messages.append({"role": "system", "content": self.config.system_instruction})
        messages.extend(self._history)
        messages.extend(input_messages)
        return messages

    async def send_message_stream(self, message: Any):
        input_messages = _input_to_messages(message)
        request_messages = self._messages_for_request(input_messages)
        kwargs = _config_to_completion_kwargs(self.config)
        stream = await _maybe_await(
            acompletion(
                model=self.model,
                messages=request_messages,
                stream=True,
                **kwargs,
            )
        )

        content_parts: list[str] = []
        tool_call_chunks: dict[int, dict[str, Any]] = {}
        finish_reason = ""

        async for chunk in stream:
            if not _get(chunk, "choices"):
                continue
            choice = _get(chunk, "choices", [])[0]
            finish = _get(choice, "finish_reason")
            if finish:
                finish_reason = _normalize_finish_reason(finish)
            delta = _get(choice, "delta", {}) or {}

            reasoning = (
                _get(delta, "reasoning_content")
                or _get(delta, "thinking")
                or _get(delta, "reasoning")
            )
            if isinstance(reasoning, str) and reasoning:
                yield types.StreamChunk(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="assistant",
                                parts=[types.Part(text=reasoning, thought=True)],
                            )
                        )
                    ]
                )

            content = _get(delta, "content")
            if isinstance(content, str) and content:
                content_parts.append(content)
                yield types.StreamChunk(
                    candidates=[
                        types.Candidate(
                            content=types.Content(
                                role="assistant",
                                parts=[types.Part(text=content)],
                            )
                        )
                    ]
                )

            for tool_call in _get(delta, "tool_calls", None) or []:
                index = int(_get(tool_call, "index", 0) or 0)
                target = tool_call_chunks.setdefault(
                    index,
                    {
                        "id": "",
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                    },
                )
                if _get(tool_call, "id"):
                    target["id"] += str(_get(tool_call, "id"))
                if _get(tool_call, "type"):
                    target["type"] = str(_get(tool_call, "type"))
                fn = _get(tool_call, "function", {}) or {}
                if _get(fn, "name"):
                    target["function"]["name"] += str(_get(fn, "name"))
                if _get(fn, "arguments"):
                    target["function"]["arguments"] += str(_get(fn, "arguments"))

        tool_calls = [
            _stream_tool_call_to_function_call(data)
            for _, data in sorted(tool_call_chunks.items())
            if (data.get("function") or {}).get("name")
        ]
        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": "".join(content_parts) or None,
        }
        if tool_calls:
            assistant_message["tool_calls"] = [
                {
                    "id": fc.id or f"call_{uuid.uuid4().hex}",
                    "type": "function",
                    "function": {
                        "name": fc.name,
                        "arguments": _json_dumps(fc.args),
                    },
                }
                for fc in tool_calls
            ]

        self._history.extend(input_messages)
        self._history.append(assistant_message)

        if tool_calls:
            yield types.StreamChunk(
                candidates=[
                    types.Candidate(
                        content=types.Content(
                            role="assistant",
                            parts=[
                                types.Part(function_call=tool_call)
                                for tool_call in tool_calls
                            ],
                        ),
                        finish_reason=finish_reason or "TOOL_CALLS",
                    )
                ]
            )
        else:
            yield types.StreamChunk(
                candidates=[
                    types.Candidate(
                        content=types.Content(role="assistant", parts=[]),
                        finish_reason=finish_reason or "STOP",
                    )
                ]
            )


class LiteLLMChats:
    def create(
        self,
        *,
        model: str,
        config: Optional[types.GenerateContentConfig] = None,
        history: Optional[list[Any]] = None,
    ) -> LiteLLMChatSession:
        return LiteLLMChatSession(model=model, config=config, history=history)


class LiteLLMAio:
    def __init__(self) -> None:
        self.models = LiteLLMModels()
        self.chats = LiteLLMChats()


class LiteLLMClient:
    def __init__(self) -> None:
        configure_litellm()
        self.aio = LiteLLMAio()
        self.models = LiteLLMSyncModels()
