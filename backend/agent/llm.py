import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import anthropic
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
        self.enabled = bool(getattr(settings, "ANTHROPIC_API_KEY", ""))
        self.model = getattr(
            settings, "ANTHROPIC_MODEL", "claude-sonnet-4-20250514"
        )
        self.client = (
            anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            if self.enabled
            else None
        )

    @staticmethod
    def _convert_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted = []
        for tool in tools:
            func = tool.get("function", tool)
            converted.append({
                "name": func["name"],
                "description": func.get("description", ""),
                "input_schema": func.get(
                    "parameters", func.get("input_schema", {})
                ),
            })
        return converted

    @staticmethod
    def _convert_messages(
        messages: list[dict[str, Any]],
    ) -> tuple[str | None, list[dict[str, Any]]]:
        system_parts: list[str] = []
        anthropic_messages: list[dict[str, Any]] = []
        i = 0

        while i < len(messages):
            msg = messages[i]
            role = msg.get("role")

            if role == "system":
                system_parts.append(msg.get("content", ""))
                i += 1

            elif role == "assistant":
                content_blocks: list[dict[str, Any]] = []
                if msg.get("content"):
                    content_blocks.append({
                        "type": "text",
                        "text": msg["content"],
                    })
                for tc in msg.get("tool_calls", []):
                    args = tc["function"]["arguments"]
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except (json.JSONDecodeError, TypeError):
                            args = {}
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["function"]["name"],
                        "input": args,
                    })
                anthropic_messages.append({
                    "role": "assistant",
                    "content": content_blocks,
                })
                i += 1

            elif role == "tool":
                tool_results: list[dict[str, Any]] = []
                while i < len(messages) and messages[i].get("role") == "tool":
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": messages[i]["tool_call_id"],
                        "content": messages[i].get("content", ""),
                    })
                    i += 1
                anthropic_messages.append({
                    "role": "user",
                    "content": tool_results,
                })

            else:
                anthropic_messages.append(msg)
                i += 1

        system = "\n\n".join(system_parts) if system_parts else None
        return system, anthropic_messages

    @staticmethod
    def _parse_response(
        response: anthropic.types.Message,
    ) -> CompletionResponse:
        content_text: str | None = None
        tool_calls: list[ToolCallInfo] = []

        for block in response.content:
            if block.type == "text":
                content_text = (content_text or "") + block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCallInfo(
                    id=block.id,
                    name=block.name,
                    arguments=json.dumps(block.input),
                ))

        return CompletionResponse(content=content_text, tool_calls=tool_calls)

    async def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> CompletionResponse:
        if not self.client:
            raise ValueError("No LLM API key configured.")

        system, anthropic_messages = self._convert_messages(messages)
        anthropic_tools = self._convert_tools(tools)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": anthropic_messages,
            "tools": anthropic_tools,
            "temperature": 0.2,
            "max_tokens": 4096,
        }
        if system:
            kwargs["system"] = system

        response = await self.client.messages.create(**kwargs)
        return self._parse_response(response)

    async def complete_with_tools_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AsyncIterator[dict[str, Any]]:
        if not self.client:
            raise ValueError("No LLM API key configured.")

        system, anthropic_messages = self._convert_messages(messages)
        anthropic_tools = self._convert_tools(tools)

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": anthropic_messages,
            "tools": anthropic_tools,
            "temperature": 0.2,
            "max_tokens": 4096,
        }
        if system:
            kwargs["system"] = system

        tool_calls_buffer: dict[int, StreamToolCallDelta] = {}
        stop_reason: str | None = None

        async with self.client.messages.stream(**kwargs) as stream:
            async for event in stream:
                if event.type == "content_block_start":
                    block = event.content_block
                    if block.type == "tool_use":
                        tool_calls_buffer[event.index] = StreamToolCallDelta(
                            index=event.index,
                            id=block.id,
                            function=StreamFunctionDelta(name=block.name),
                        )

                elif event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        yield {
                            "delta": StreamDelta(content=delta.text),
                            "finish_reason": None,
                        }
                    elif delta.type == "input_json_delta":
                        idx = event.index
                        if idx in tool_calls_buffer:
                            tc = tool_calls_buffer[idx]
                            existing = tc.function.arguments or ""
                            tc.function.arguments = existing + delta.partial_json

                elif event.type == "message_delta":
                    stop_reason = event.delta.stop_reason

        assembled = [tool_calls_buffer[i] for i in sorted(tool_calls_buffer)]
        finish = (
            "tool_calls" if assembled and stop_reason == "tool_use" else "stop"
        )

        yield {
            "delta": StreamDelta(
                tool_calls=assembled if assembled else None,
            ),
            "finish_reason": finish,
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
