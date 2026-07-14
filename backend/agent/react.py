from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, TYPE_CHECKING

from asgiref.sync import sync_to_async

from agent.goals import GoalStack
from agent.memory import ConversationMemory
from agent.llm import LLMClient, tool_arguments
from agent.tools.base import ToolResult

if TYPE_CHECKING:
    from agent.tools.base import BaseTool

logger = logging.getLogger(__name__)

MAX_REACT_ITERATIONS = 10
REFLECTION_PROMPT = (
    "Review the tool result above. If you have enough information to fully answer "
    "the user's request, respond with a final answer now. If you still need to call "
    "additional tools to complete the task, call the next tool. If a tool failed or "
    "returned unexpected data, reason about an alternative approach. Never repeat the "
    "exact same tool call."
)

ToolTraceCallback = Callable[[str, dict[str, Any], ToolResult], None]


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
    goals: GoalStack | None = None


class ReActLoop:
    def __init__(self, llm: LLMClient, tools: dict[str, BaseTool]) -> None:
        self.llm = llm
        self.tools = tools
        self._tool_trace_callback: ToolTraceCallback | None = None

    def set_tool_trace_callback(self, callback: ToolTraceCallback | None) -> None:
        self._tool_trace_callback = callback

    def _build_goal_context(self, goals: GoalStack) -> str:
        if not goals:
            return ""
        return f"\n\nCurrent goal stack:\n{goals.as_context()}"

    def _build_system_with_goals(
        self,
        system_messages: list[dict[str, Any]],
        goals: GoalStack,
    ) -> list[dict[str, Any]]:
        if not goals:
            return list(system_messages)
        messages = list(system_messages)
        goal_msg = {"role": "system", "content": self._build_goal_context(goals)}
        messages.append(goal_msg)
        return messages

    def _tools_as_openai(self) -> list[dict[str, Any]]:
        return [tool.to_openai_tool() for tool in self.tools.values()]

    async def run(
        self,
        system_messages: list[dict[str, Any]],
        user_message: str,
        memory: ConversationMemory,
    ) -> ReActResult:
        goals = GoalStack()
        messages = list(system_messages)
        steps: list[ReActStep] = []

        if self._user_requests_planning(user_message):
            messages.append({
                "role": "system",
                "content": (
                    "This is a multi-part request. Break it into specific goals "
                    "and work through them one at a time. Push each as a goal."
                ),
            })

        messages.append({"role": "user", "content": user_message})

        for iteration in range(1, MAX_REACT_ITERATIONS + 1):
            response = await self.llm.complete_with_tools(
                messages,
                self._tools_as_openai(),
            )

            assistant_msg: dict[str, Any] = {"role": "assistant"}
            if response.content:
                assistant_msg["content"] = response.content
            if response.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments,
                        },
                    }
                    for tc in response.tool_calls
                ]
            messages.append(assistant_msg)

            if not response.tool_calls:
                final_content = (
                    response.content
                    or "I handled that, but I do not have more detail."
                )
                return ReActResult(
                    response=final_content,
                    steps=steps,
                    messages=messages,
                    goals=goals,
                )

            for tc in response.tool_calls:
                step = ReActStep(
                    iteration=iteration,
                    thought=response.content or "",
                    tool_name=tc.name,
                    tool_args=tool_arguments(tc.arguments),
                    tool_call_id=tc.id,
                )

                result = await self._execute_tool(tc.name, step.tool_args, memory)
                step.observation = result.message
                step.tool_success = result.success
                steps.append(step)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result.to_llm_content(),
                })

            goal_context = self._build_goal_context(goals)
            messages.append({
                "role": "system",
                "content": f"{REFLECTION_PROMPT}\n\n{goal_context}",
            })

        return ReActResult(
            response="I used several tools but need one more detail to finish. Could you clarify?",
            steps=steps,
            messages=messages,
            goals=goals,
        )

    async def run_stream(
        self,
        system_messages: list[dict[str, Any]],
        user_message: str,
        memory: ConversationMemory,
    ) -> AsyncIterator[dict[str, Any]]:
        goals = GoalStack()
        messages = list(system_messages)
        steps: list[ReActStep] = []

        if self._user_requests_planning(user_message):
            messages.append({
                "role": "system",
                "content": (
                    "This is a multi-part request. Break it into specific goals "
                    "and work through them one at a time. Push each as a goal."
                ),
            })

        messages.append({"role": "user", "content": user_message})

        full_response = ""

        for iteration in range(1, MAX_REACT_ITERATIONS + 1):
            tool_calls_buffer: dict[int, dict[str, Any]] = {}
            content_buffer = ""

            async for event in self.llm.complete_with_tools_stream(
                messages,
                self._tools_as_openai(),
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
                                tool_calls_buffer[idx]["function"]["name"] = (
                                    tc.function.name
                                )
                            if tc.function.arguments:
                                tool_calls_buffer[idx]["function"]["arguments"] += (
                                    tc.function.arguments
                                )

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
                        "goals": goals.as_dicts(),
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
                    "response": full_response
                    or "I handled that, but I do not have more detail.",
                    "steps": len(steps),
                    "goals": goals.as_dicts(),
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

                if result.data and result.data.get("confirmation_required"):
                    action_type = self._detect_action_type(func_name, result)
                    if action_type:
                        yield {
                            "type": "action_required",
                            "action": action_type,
                            "description": result.message,
                            "params": result.data,
                        }

                messages.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": result.to_llm_content(),
                })

            goal_context = self._build_goal_context(goals)
            messages.append({
                "role": "system",
                "content": f"{REFLECTION_PROMPT}\n\n{goal_context}",
            })

        yield {
            "type": "done",
            "response": full_response
            or "I used several tools but need one more detail to finish.",
            "steps": len(steps),
            "goals": goals.as_dicts(),
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
        start_time = time.monotonic()
        result = await sync_to_async(tool.execute)(**args)
        duration_ms = int((time.monotonic() - start_time) * 1000)
        memory.remember_tool_result(result, tool_name=name)
        logger.info(
            "ReAct tool=%s success=%s duration_ms=%d",
            name,
            result.success,
            duration_ms,
        )
        if self._tool_trace_callback:
            self._tool_trace_callback(name, args, result)
        return result

    def _detect_action_type(self, tool_name: str, result: ToolResult) -> str | None:
        if tool_name == "process_payment" and result.data and result.data.get("confirmation_required"):
            return "confirm_payment"
        if tool_name == "manage_order" and result.data and result.data.get("confirmation_required"):
            return "confirm_order"
        if tool_name == "manage_reservation" and result.data and result.data.get("reservation"):
            reservation = result.data["reservation"]
            if reservation.get("status") == "held":
                return "confirm_reservation"
        return None

    def _user_requests_planning(self, message: str) -> bool:
        indicators = ["and", "&", "also", "plus", "then", "after that", "as well as"]
        text = message.lower()
        return sum(1 for w in indicators if w in text) >= 2
