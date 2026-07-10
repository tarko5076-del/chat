from typing import Any

from openai import OpenAIError

from app.agent.memory import ConversationMemory
from app.agent.order_workflow import OrderWorkflow
from app.agent.planner import LocalPlanner
from app.agent.prompts import system_prompt
from app.llm.client import LLMClient, tool_arguments
from app.tools import BillingTool, FAQTool, MenuTool, OrderTool, PaymentTool, ReservationTool
from app.tools.base import BaseTool, ToolResult


class RestaurantAgent:
    def __init__(self) -> None:
        self.tools = self._build_tools()
        self.llm = LLMClient()
        self.planner = LocalPlanner()
        self.order_workflow = OrderWorkflow(self)

    async def run(
        self,
        message: str,
        history: list[dict] | None = None,
        memory: ConversationMemory | None = None,
    ) -> str:
        if not message.strip():
            raise ValueError("Message cannot be empty.")

        memory = memory or ConversationMemory.from_history(history)
        memory.remember_user_message(message)

        workflow_response = await self.order_workflow.handle(message, memory)
        if workflow_response:
            memory.remember_message(workflow_response)
            return workflow_response

        if self.llm.enabled:
            try:
                response = await self._run_with_llm(message, history or [], memory)
            except OpenAIError:
                response = await self._run_locally(message, memory)
            except Exception:
                response = await self._run_locally(message, memory)
        else:
            response = await self._run_locally(message, memory)
        memory.remember_message(response)
        return response

    async def _run_with_llm(
        self,
        message: str,
        history: list[dict],
        memory: ConversationMemory,
    ) -> str:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt()},
            {"role": "system", "content": f"Conversation memory: {memory.as_context()}"},
            *history[-12:],
            {"role": "user", "content": message},
        ]

        for _ in range(4):
            response = await self.llm.complete_with_tools(
                messages,
                [tool.to_openai_tool() for tool in self.tools.values()],
            )
            assistant = response.choices[0].message
            messages.append(assistant.model_dump(exclude_none=True))
            if not assistant.tool_calls:
                return assistant.content or "I handled that, but I do not have more detail."
            for call in assistant.tool_calls:
                result = await self._execute_tool(
                    call.function.name,
                    tool_arguments(call.function.arguments),
                    memory,
                )
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": result.to_llm_content()}
                )
        return "I used several tools, but I need one more detail to finish that request."

    async def _run_locally(self, message: str, memory: ConversationMemory) -> str:
        plan = self.planner.plan(message, memory)
        results = [
            await self._execute_tool(step["tool"], step["args"], memory)
            for step in plan
        ]
        return self._natural_response(results)

    async def _execute_tool(
        self,
        name: str,
        args: dict[str, Any],
        memory: ConversationMemory,
    ) -> ToolResult:
        tool = self.tools.get(name)
        if not tool:
            return ToolResult(success=False, message=f"Tool '{name}' is not available.")
        result = await tool.execute(**args)
        memory.remember_tool_result(result)
        return result

    def _natural_response(self, results: list[ToolResult]) -> str:
        joined = "\n\n".join(result.to_text() for result in results)
        missing_fields = [
            field
            for result in results
            for field in result.missing_fields
        ]
        if missing_fields:
            return self._missing_fields_response(missing_fields)
        return joined

    def _missing_fields_response(self, fields: list[str]) -> str:
        labels = {
            "customer_name": "customer name",
            "phone": "phone number",
            "email": "email address",
            "reservation_date": "reservation date",
            "reservation_time": "reservation time",
            "party_size": "party size",
            "reservation_id": "reservation ID",
            "order_id": "order ID",
            "item_name": "menu item",
            "customer_identifier": "email address, phone number, or order number",
            "delivery_method": "pickup or delivery preference",
            "delivery_address": "delivery address",
            "payment_method": "payment method",
        }
        unique = []
        for field in fields:
            label = labels.get(field, field.replace("_", " "))
            if label not in unique:
                unique.append(label)
        if len(unique) == 1:
            requested = unique[0]
        else:
            requested = f"{', '.join(unique[:-1])}, and {unique[-1]}"
        return f"I can help with that. What {requested} should I use?"

    def _build_tools(self) -> dict[str, BaseTool]:
        tools = [MenuTool(), FAQTool(), ReservationTool(), OrderTool(), BillingTool(), PaymentTool()]
        return {tool.name: tool for tool in tools}


agent = RestaurantAgent()
