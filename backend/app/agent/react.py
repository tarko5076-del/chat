from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, TYPE_CHECKING

from app.agent.memory import ConversationMemory
from app.llm.client import LLMClient, tool_arguments
from app.tools.base import ToolResult

if TYPE_CHECKING:
    from app.tools.base import BaseTool

logger = logging.getLogger(__name__)

MAX_REACT_ITERATIONS = 10
REFLECTION_PROMPT = (
    "Review the tool result above. If you have enough information to fully answer "
    "the user's request, respond with a final answer now. If you still need to call "
    "additional tools to complete the task, call the next tool. If a tool failed or "
    "returned unexpected data, reason about an alternative approach. Never repeat the "
    "exact same tool call."
)


@dataclass
class ReActStep:
    iteration: int
    thought: str
    tool_name: str | None = None
    tool_args: dict[str, Any] = field(default_factory=dict)
    tool_call_id: str | None = None
    observation: str | None = None
    tool_success: bool | None = None


@dataclass
class ReActResult:
    response: str
    steps: list[ReActStep]
    messages: list[dict[str, Any]]


class ReActLoop:
    """Orchestrates the Thought -> Action -> Observation -> Re-plan cycle."""

    def __init__(self, llm: LLMClient, tools: dict[str, BaseTool]) -> None:
        self.llm = llm
        self.tools = tools

    async def run(
        self,
        system_messages: list[dict[str, Any]],
        user_message: str,
        memory: ConversationMemory,
    ) -> ReActResult:
        messages = list(system_messages)
        steps: list[ReActStep] = []

        if self._user_requests_planning(user_message):
            messages.append({
                "role": "system",
                "content": "Break this into a clear plan before calling tools.",
            })

        messages.append({"role": "user", "content": user_message})

        for iteration in range(1, MAX_REACT_ITERATIONS + 1):
            response = await self.llm.complete_with_tools(
                messages,
                [tool.to_openai_tool() for tool in self.tools.values()],
            )
            assistant = response.choices[0].message
            messages.append(assistant.model_dump(exclude_none=True))

            if not assistant.tool_calls:
                final_content = assistant.content or "I handled that, but I do not have more detail."
                return ReActResult(
                    response=final_content,
                    steps=steps,
                    messages=messages,
                )

            for call in assistant.tool_calls:
                step = ReActStep(
                    iteration=iteration,
                    thought=assistant.content or "",
                    tool_name=call.function.name,
                    tool_args=tool_arguments(call.function.arguments),
                    tool_call_id=call.id,
                )

                result = await self._execute_tool(
                    call.function.name,
                    step.tool_args,
                    memory,
                )
                step.observation = result.message
                step.tool_success = result.success
                steps.append(step)

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result.to_llm_content(),
                })

            messages.append({"role": "system", "content": REFLECTION_PROMPT})

        return ReActResult(
            response="I used several tools but need one more detail to finish. Could you clarify?",
            steps=steps,
            messages=messages,
        )

    async def run_stream(
        self,
        system_messages: list[dict[str, Any]],
        user_message: str,
        memory: ConversationMemory,
    ) -> AsyncIterator[dict[str, Any]]:
        """Streaming version of run(). Yields SSE events."""
        messages = list(system_messages)
        steps: list[ReActStep] = []

        if self._user_requests_planning(user_message):
            messages.append({
                "role": "system",
                "content": "Break this into a clear plan before calling tools.",
            })

        messages.append({"role": "user", "content": user_message})

        full_response = ""

        for iteration in range(1, MAX_REACT_ITERATIONS + 1):
            tool_calls_buffer: dict[str, dict[str, Any]] = {}
            current_tool_calls: list[dict[str, Any]] = []
            content_buffer = ""

            async for event in self.llm.complete_with_tools_stream(
                messages,
                [tool.to_openai_tool() for tool in self.tools.values()],
            ):
                delta = event["delta"]
                finish_reason = event["finish_reason"]

                if delta.content:
                    content_buffer += delta.content
                    full_response += delta.content
                    yield {"type": "token", "content": delta.content}

                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_buffer:
                            tool_calls_buffer[idx] = {
                                "id": tc.id or "",
                                "function": {"name": "", "arguments": ""},
                            }
                        if tc.id:
                            tool_calls_buffer[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_buffer[idx]["function"]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls_buffer[idx]["function"]["arguments"] += tc.function.arguments

                if finish_reason == "stop":
                    if content_buffer:
                        messages.append({
                            "role": "assistant",
                            "content": content_buffer,
                        })
                    yield {
                        "type": "done",
                        "response": full_response,
                        "steps": len(steps),
                    }
                    return

                if finish_reason == "tool_calls":
                    break

            assembled_calls = []
            for idx in sorted(tool_calls_buffer.keys()):
                tc_data = tool_calls_buffer[idx]
                if tc_data["function"]["name"]:
                    assembled_calls.append(tc_data)

            if not assembled_calls:
                if content_buffer:
                    messages.append({
                        "role": "assistant",
                        "content": content_buffer,
                    })
                yield {
                    "type": "done",
                    "response": full_response or "I handled that, but I do not have more detail.",
                    "steps": len(steps),
                }
                return

            assistant_msg: dict[str, Any] = {"role": "assistant"}
            if content_buffer:
                assistant_msg["content"] = content_buffer
            assistant_msg["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": tc["function"],
                }
                for tc in assembled_calls
            ]
            messages.append(assistant_msg)

            for tc in assembled_calls:
                call_id = tc["id"]
                func_name = tc["function"]["name"]
                func_args = tool_arguments(tc["function"]["arguments"])

                step = ReActStep(
                    iteration=iteration,
                    thought=content_buffer,
                    tool_name=func_name,
                    tool_args=func_args,
                    tool_call_id=call_id,
                )

                yield {
                    "type": "tool_start",
                    "tool": func_name,
                    "args": func_args,
                }

                result = await self._execute_tool(func_name, func_args, memory)
                step.observation = result.message
                step.tool_success = result.success
                steps.append(step)

                yield {
                    "type": "tool_result",
                    "tool": func_name,
                    "success": result.success,
                    "message": result.message,
                }

                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": result.to_llm_content(),
                })

            messages.append({"role": "system", "content": REFLECTION_PROMPT})

        yield {
            "type": "done",
            "response": full_response or "I used several tools but need one more detail to finish.",
            "steps": len(steps),
        }

    async def _execute_tool(
        self,
        name: str,
        args: dict[str, Any],
        memory: ConversationMemory,
    ) -> ToolResult:
        tool = self.tools.get(name)
        if not tool:
            return ToolResult(
                success=False,
                message=f"Tool '{name}' is not available.",
            )
        result = await tool.execute(**args)
        memory.remember_tool_result(result)
        logger.info(
            "ReAct tool=%s success=%s",
            name,
            result.success,
        )
        return result

    def _user_requests_planning(self, message: str) -> bool:
        indicators = ["and", "&", "also", "plus", "then", "after that", "as well as"]
        text = message.lower()
        return sum(1 for w in indicators if w in text) >= 2
