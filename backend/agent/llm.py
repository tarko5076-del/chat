import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import openai
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass
class ToolCallInfo:
    id: str
    name: str
    arguments: str


@dataclass
class CompletionResponse:
    content: str | None
    tool_calls: list[ToolCallInfo]


class StreamDelta:
    def __init__(
        self,
        content: str | None = None,
        tool_calls: list | None = None,
    ) -> None:
        self.content = content
        self.tool_calls = tool_calls


@dataclass
class StreamFunctionDelta:
    name: str | None = None
    arguments: str | None = None


@dataclass
class StreamToolCallDelta:
    index: int = 0
    id: str | None = None
    function: StreamFunctionDelta = field(default_factory=StreamFunctionDelta)


class LLMClient:
    def __init__(self) -> None:
        api_key = getattr(settings, "LLM_API_KEY", "")
        base_url = getattr(settings, "LLM_BASE_URL", "")
        self.enabled = bool(api_key)
        self.model = getattr(settings, "LLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct")

        if self.enabled:
            kwargs: dict[str, Any] = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self.client = openai.AsyncOpenAI(**kwargs)
        else:
            self.client = None

    @staticmethod
    def _parse_response(response: Any) -> CompletionResponse:
        choice = response.choices[0]
        message = choice.message

        content_text = message.content or None
        tool_calls: list[ToolCallInfo] = []

        if message.tool_calls:
            for tc in message.tool_calls:
                tool_calls.append(ToolCallInfo(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=tc.function.arguments,
                ))

        return CompletionResponse(content=content_text, tool_calls=tool_calls)

    async def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> CompletionResponse:
        if not self.client:
            raise ValueError("No LLM API key configured. Set LLM_API_KEY in your environment.")

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 4096,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await self.client.chat.completions.create(**kwargs)
        return self._parse_response(response)

    async def complete_with_tools_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AsyncIterator[dict[str, Any]]:
        if not self.client:
            raise ValueError("No LLM API key configured. Set LLM_API_KEY in your environment.")

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 4096,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        tool_calls_buffer: dict[int, StreamToolCallDelta] = {}

        stream = await self.client.chat.completions.create(**kwargs)
        async for chunk in stream:
            choice = chunk.choices[0] if chunk.choices else None
            if not choice:
                continue

            delta = choice.delta
            finish_reason = choice.finish_reason

            if delta and delta.content:
                yield {
                    "delta": StreamDelta(content=delta.content),
                    "finish_reason": None,
                }

            if delta and delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_buffer:
                        tool_calls_buffer[idx] = StreamToolCallDelta(
                            index=idx,
                            id=tc_delta.id or "",
                            function=StreamFunctionDelta(
                                name=tc_delta.function.name if tc_delta.function else None,
                                arguments="",
                            ),
                        )
                    else:
                        if tc_delta.id:
                            tool_calls_buffer[idx].id = tc_delta.id

                    if tc_delta.function:
                        if tc_delta.function.name:
                            tool_calls_buffer[idx].function.name = tc_delta.function.name
                        if tc_delta.function.arguments:
                            existing = tool_calls_buffer[idx].function.arguments or ""
                            tool_calls_buffer[idx].function.arguments = (
                                existing + tc_delta.function.arguments
                            )

            if finish_reason:
                assembled = [tool_calls_buffer[i] for i in sorted(tool_calls_buffer)]

                if finish_reason == "tool_calls" and assembled:
                    yield {
                        "delta": StreamDelta(tool_calls=assembled),
                        "finish_reason": "tool_calls",
                    }
                else:
                    yield {
                        "delta": StreamDelta(),
                        "finish_reason": "stop",
                    }
                return

        assembled = [tool_calls_buffer[i] for i in sorted(tool_calls_buffer)]
        if assembled:
            yield {
                "delta": StreamDelta(tool_calls=assembled),
                "finish_reason": "tool_calls",
            }
        else:
            yield {
                "delta": StreamDelta(),
                "finish_reason": "stop",
            }


def tool_arguments(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Model returned invalid tool JSON: %s", raw)
        return {}
    return parsed if isinstance(parsed, dict) else {}
