import json
import logging
from typing import Any, AsyncIterator

from openai import OpenAIError
from sqlalchemy.orm import Session

from app.agent.memory import ConversationMemory
from app.agent.memory_manager import MemoryManager
from app.agent.order_workflow import OrderWorkflow
from app.agent.planner import LocalPlanner
from app.agent.prompts import system_prompt
from app.agent.react import ReActLoop
from app.core.config import MAX_HISTORY_MESSAGES
from app.database import SessionLocal
from app.llm.client import LLMClient
from app.tools import BillingTool, FAQTool, MenuTool, OrderTool, PaymentTool, ReservationTool
from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class RestaurantAgent:
    def __init__(self) -> None:
        self.tools = self._build_tools()
        self.llm = LLMClient()
        self.planner = LocalPlanner()
        self.react = ReActLoop(self.llm, self.tools)
        self.order_workflow = OrderWorkflow(self)
        self.memory_manager = MemoryManager()

    async def run(
        self,
        message: str,
        history: list[dict] | None = None,
        memory: ConversationMemory | None = None,
        *,
        customer_id: str | None = None,
        conversation_id: str | None = None,
    ) -> str:
        if not message.strip():
            raise ValueError("Message cannot be empty.")

        memory = memory or ConversationMemory.from_history(history)
        memory.remember_user_message(message)

        db = SessionLocal()
        try:
            self.memory_manager.record_user_message(
                db,
                customer_id=customer_id,
                conversation_id=conversation_id,
                message=message,
            )
            db.commit()
        except Exception:
            logger.debug("Failed to record episodic event", exc_info=True)
        finally:
            db.close()

        workflow_response = await self.order_workflow.handle(message, memory)
        if workflow_response:
            memory.remember_message(workflow_response)
            return workflow_response

        if self.llm.enabled:
            try:
                response = await self._run_with_react(
                    message, history or [], memory,
                    customer_id=customer_id,
                    conversation_id=conversation_id,
                )
            except OpenAIError:
                logger.warning("LLM call failed, falling back to local planner")
                response = await self._run_locally(message, memory)
            except Exception:
                logger.exception("Unexpected error in ReAct loop, falling back to local planner")
                response = await self._run_locally(message, memory)
        else:
            response = await self._run_locally(message, memory)

        memory.remember_message(response)

        db = SessionLocal()
        try:
            self.memory_manager.record_assistant_response(
                db,
                customer_id=customer_id,
                conversation_id=conversation_id,
                response=response,
            )
            if customer_id:
                self.memory_manager.extract_and_learn(
                    db,
                    customer_id=customer_id,
                    conversation_id=conversation_id,
                    working_memory=memory,
                )
                self.memory_manager.update_profile(db, customer_id=customer_id)
            db.commit()
        except Exception:
            logger.debug("Failed to record episodic/semantic events", exc_info=True)
        finally:
            db.close()

        return response

    async def run_stream(
        self,
        message: str,
        history: list[dict] | None = None,
        memory: ConversationMemory | None = None,
        *,
        customer_id: str | None = None,
        conversation_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Streaming version of run(). Yields SSE events."""
        if not message.strip():
            raise ValueError("Message cannot be empty.")

        memory = memory or ConversationMemory.from_history(history)
        memory.remember_user_message(message)

        db = SessionLocal()
        try:
            self.memory_manager.record_user_message(
                db,
                customer_id=customer_id,
                conversation_id=conversation_id,
                message=message,
            )
            db.commit()
        except Exception:
            logger.debug("Failed to record episodic event", exc_info=True)
        finally:
            db.close()

        workflow_response = await self.order_workflow.handle(message, memory)
        if workflow_response:
            memory.remember_message(workflow_response)
            yield {"type": "token", "content": workflow_response}
            yield {"type": "done", "response": workflow_response, "steps": 0}
            return

        if self.llm.enabled:
            try:
                async for event in self._run_with_react_stream(
                    message, history or [], memory,
                    customer_id=customer_id,
                    conversation_id=conversation_id,
                ):
                    yield event
                return
            except OpenAIError:
                logger.warning("LLM call failed, falling back to local planner")
            except Exception:
                logger.exception("Unexpected error in ReAct stream, falling back to local planner")

        response = await self._run_locally(message, memory)
        memory.remember_message(response)
        yield {"type": "token", "content": response}
        yield {"type": "done", "response": response, "steps": 0}

    async def _run_with_react(
        self,
        message: str,
        history: list[dict],
        memory: ConversationMemory,
        *,
        customer_id: str | None = None,
        conversation_id: str | None = None,
    ) -> str:
        memory_context = f"Conversation memory: {memory.as_context()}"

        db = SessionLocal()
        try:
            long_term = self.memory_manager.build_context_string(db, customer_id=customer_id)
            if long_term:
                memory_context += f"\n{long_term}"
        except Exception:
            logger.debug("Failed to load long-term memory context", exc_info=True)
        finally:
            db.close()

        system_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt()},
            {"role": "system", "content": memory_context},
            *history[-MAX_HISTORY_MESSAGES:],
        ]

        db = SessionLocal()
        try:
            self.react.set_tool_trace_callback(
                lambda name, args, result: self._trace_tool(
                    db, name, args, result,
                    customer_id=customer_id,
                    conversation_id=conversation_id,
                )
            )
            result = await self.react.run(system_messages, message, memory)
        finally:
            self.react.set_tool_trace_callback(None)
            db.close()

        for step in result.steps:
            if step.tool_name:
                logger.info(
                    "ReAct step %d: tool=%s success=%s",
                    step.iteration,
                    step.tool_name,
                    step.tool_success,
                )

        if result.goals:
            completed = sum(1 for g in result.goals if g.status.value == "completed")
            failed = sum(1 for g in result.goals if g.status.value == "failed")
            logger.info(
                "Goals: %d completed, %d failed, %d total",
                completed,
                failed,
                len(result.goals),
            )

        return result.response

    async def _run_with_react_stream(
        self,
        message: str,
        history: list[dict],
        memory: ConversationMemory,
        *,
        customer_id: str | None = None,
        conversation_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Streaming version of _run_with_react."""
        memory_context = f"Conversation memory: {memory.as_context()}"

        db = SessionLocal()
        try:
            long_term = self.memory_manager.build_context_string(db, customer_id=customer_id)
            if long_term:
                memory_context += f"\n{long_term}"
        except Exception:
            logger.debug("Failed to load long-term memory context", exc_info=True)
        finally:
            db.close()

        system_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt()},
            {"role": "system", "content": memory_context},
            *history[-MAX_HISTORY_MESSAGES:],
        ]

        final_response = ""
        final_goals: list[dict[str, str]] = []

        db = SessionLocal()
        try:
            self.react.set_tool_trace_callback(
                lambda name, args, result: self._trace_tool(
                    db, name, args, result,
                    customer_id=customer_id,
                    conversation_id=conversation_id,
                )
            )
            async for event in self.react.run_stream(system_messages, message, memory):
                if event["type"] == "done":
                    final_response = event["response"]
                    final_goals = event.get("goals", [])
                yield event
        finally:
            self.react.set_tool_trace_callback(None)
            db.close()

        if final_response:
            memory.remember_message(final_response)

        if final_goals:
            completed = sum(1 for g in final_goals if g.get("status") == "completed")
            failed = sum(1 for g in final_goals if g.get("status") == "failed")
            logger.info(
                "Goals: %d completed, %d failed, %d total",
                completed,
                failed,
                len(final_goals),
            )

    def _trace_tool(
        self,
        db: Session,
        name: str,
        args: dict[str, Any],
        result: ToolResult,
        *,
        customer_id: str | None = None,
        conversation_id: str | None = None,
    ) -> None:
        try:
            self.memory_manager.record_tool_event(
                db,
                customer_id=customer_id,
                conversation_id=conversation_id,
                tool_name=name,
                tool_args=args,
                result=result,
            )
            db.commit()
        except Exception:
            logger.debug("Failed to trace tool event", exc_info=True)
            db.rollback()

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
