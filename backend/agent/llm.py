import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import openai
from django.conf import settings

logger = logging.getLogger(__name__)

LLM_MAX_RETRIES = 3
LLM_RETRY_BASE_DELAY = 1.0
LLM_RETRY_MAX_DELAY = 16.0


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

        fallback_key = getattr(settings, "LLM_FALLBACK_API_KEY", "")
        fallback_url = getattr(settings, "LLM_FALLBACK_BASE_URL", "")
        self.fallback_model = getattr(settings, "LLM_FALLBACK_MODEL", "")
        self.fallback_enabled = bool(fallback_key)

        if self.enabled:
            kwargs: dict[str, Any] = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self.client = openai.AsyncOpenAI(**kwargs)
        else:
            self.client = None

        if self.fallback_enabled:
            fb_kwargs: dict[str, Any] = {"api_key": fallback_key}
            if fallback_url:
                fb_kwargs["base_url"] = fallback_url
            self.fallback_client = openai.AsyncOpenAI(**fb_kwargs)
        else:
            self.fallback_client = None

    def _build_kwargs(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
        stream: bool = False,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 4096,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        if stream:
            kwargs["stream"] = True
        return kwargs

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

    def _is_retryable(self, exc: Exception) -> bool:
        if isinstance(exc, openai.RateLimitError):
            return True
        if isinstance(exc, openai.APIStatusError) and exc.status_code in (429, 500, 502, 503, 504):
            return True
        if isinstance(exc, (openai.APITimeoutError, openai.APIConnectionError)):
            return True
        if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
            return True
        return False

    async def _call_primary(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], stream: bool = False,
    ) -> Any:
        kwargs = self._build_kwargs(messages, tools, self.model, stream=stream)
        return await self.client.chat.completions.create(**kwargs)

    async def _call_fallback(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]], stream: bool = False,
    ) -> Any:
        kwargs = self._build_kwargs(messages, tools, self.fallback_model, stream=stream)
        return await self.fallback_client.chat.completions.create(**kwargs)

    async def _retry_with_fallback(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        stream: bool = False,
    ) -> Any:
        last_exc: Exception | None = None

        for attempt in range(LLM_MAX_RETRIES):
            try:
                return await self._call_primary(messages, tools, stream=stream)
            except Exception as exc:
                last_exc = exc
                if not self._is_retryable(exc):
                    break
                delay = min(LLM_RETRY_BASE_DELAY * (2 ** attempt), LLM_RETRY_MAX_DELAY)
                logger.warning(
                    "LLM primary attempt %d/%d failed (%s), retrying in %.1fs",
                    attempt + 1, LLM_MAX_RETRIES, exc.__class__.__name__, delay,
                )
                await asyncio.sleep(delay)

        if self.fallback_enabled:
            logger.warning("Primary LLM exhausted, falling back to %s", self.fallback_model)
            for attempt in range(LLM_MAX_RETRIES):
                try:
                    return await self._call_fallback(messages, tools, stream=stream)
                except Exception as exc:
                    last_exc = exc
                    if not self._is_retryable(exc):
                        break
                    delay = min(LLM_RETRY_BASE_DELAY * (2 ** attempt), LLM_RETRY_MAX_DELAY)
                    logger.warning(
                        "LLM fallback attempt %d/%d failed (%s), retrying in %.1fs",
                        attempt + 1, LLM_MAX_RETRIES, exc.__class__.__name__, delay,
                    )
                    await asyncio.sleep(delay)

        raise last_exc or RuntimeError("All LLM attempts failed")

    async def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> CompletionResponse:
        if not self.client:
            raise ValueError("No LLM API key configured. Set LLM_API_KEY in your environment.")

        response = await self._retry_with_fallback(messages, tools, stream=False)
        return self._parse_response(response)

    async def complete_with_tools_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AsyncIterator[dict[str, Any]]:
        if not self.client:
            raise ValueError("No LLM API key configured. Set LLM_API_KEY in your environment.")

        stream = await self._retry_with_fallback(messages, tools, stream=True)
        tool_calls_buffer: dict[int, StreamToolCallDelta] = {}

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
