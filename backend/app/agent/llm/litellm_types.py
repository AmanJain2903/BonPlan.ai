"""Small compatibility types around LiteLLM's OpenAI-style interface.

The planner code only needs a narrow set of concepts: tool declarations,
chat-generation config, text parts, tool calls, and tool responses. Keeping
those concepts local avoids coupling graph nodes to any one provider SDK.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class FunctionDeclaration:
    name: str
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description or "",
                "parameters": self.parameters or {"type": "object", "properties": {}},
            },
        }

    def model_dump(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass
class Tool:
    function_declarations: list[FunctionDeclaration] = field(default_factory=list)

    def to_openai_tools(self) -> list[dict[str, Any]]:
        return [decl.to_openai_tool() for decl in self.function_declarations]

    def model_dump(self) -> dict[str, Any]:
        return {
            "function_declarations": [
                decl.model_dump() for decl in self.function_declarations
            ]
        }


@dataclass
class AutomaticFunctionCallingConfig:
    disable: bool = True


@dataclass
class GenerateContentConfig:
    tools: Optional[list[Tool]] = None
    system_instruction: Optional[str] = None
    temperature: Optional[float] = None
    max_output_tokens: Optional[int] = None
    automatic_function_calling: Optional[AutomaticFunctionCallingConfig] = None
    response_mime_type: Optional[str] = None
    response_json_schema: Optional[dict[str, Any]] = None
    response_format: Any = None


@dataclass
class FunctionCall:
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    id: Optional[str] = None


@dataclass
class FunctionResponse:
    name: str
    response: dict[str, Any]
    tool_call_id: Optional[str] = None


@dataclass
class Part:
    text: Optional[str] = None
    function_call: Optional[FunctionCall] = None
    function_response: Optional[FunctionResponse] = None
    thought: bool = False

    @classmethod
    def from_text(cls, text: str) -> "Part":
        return cls(text=text)

    @classmethod
    def from_function_response(
        cls,
        *,
        name: str,
        response: dict[str, Any],
        tool_call_id: Optional[str] = None,
    ) -> "Part":
        return cls(
            function_response=FunctionResponse(
                name=name,
                response=response,
                tool_call_id=tool_call_id,
            )
        )


@dataclass
class Content:
    role: str
    parts: list[Part] = field(default_factory=list)


@dataclass
class Candidate:
    content: Optional[Content] = None
    finish_reason: Optional[str] = None


@dataclass
class StreamChunk:
    candidates: list[Candidate] = field(default_factory=list)

