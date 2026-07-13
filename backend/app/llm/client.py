import json
import logging
from typing import Any, AsyncIterator

from openai import AsyncOpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    def __init__(self) -> None:
        self.enabled = bool(settings.openai_api_key)
        self.model = settings.llm_model
        self.client = self._build_client() if self.enabled else None

    def _build_client(self) -> AsyncOpenAI:
        kwargs: dict[str, str] = {"api_key": settings.llm_api_key}
        if settings.llm_base_url:
            kwargs["base_url"] = settings.llm_base_url
        return AsyncOpenAI(**kwargs)

    async def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> Any:
        if not self.client:
            raise ValueError("No LLM API key configured.")
        return await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.2,
        )

    async def complete_with_tools_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> AsyncIterator[dict[str, Any]]:
        if not self.client:
            raise ValueError("No LLM API key configured.")
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.2,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta:
                yield {
                    "chunk": chunk,
                    "delta": delta,
                    "finish_reason": chunk.choices[0].finish_reason if chunk.choices else None,
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
