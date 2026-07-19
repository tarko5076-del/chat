import json
import logging
from typing import Any, AsyncIterator

from asgiref.sync import sync_to_async

from agent.llm import LLMClient
from agent.memory import ConversationMemory
from agent.memory_engine import MemoryEngine, get_suggestions, get_greeting, inline_extract
from agent.memory_manager import MemoryManager
from agent.order_workflow import OrderWorkflow
from agent.planner import LocalPlanner
from agent.reservation_workflow import ReservationWorkflow
from agent.prompts import system_prompt
from agent.rag import format_knowledge_context, search_knowledge
from agent.react import ReActLoop
from agent.summarizer import persist_summary
from agent.tools import (
    BillingTool,
    CheckoutCartTool,
    EscalationTool,
    FAQTool,
    GetMenuItemDetailsTool,
    ManageCartTool,
    MenuTool,
    OrderTool,
    ManagePreferencesTool,
    PaymentTool,
    RecommendMenuTool,
    ReservationTool,
    SearchKnowledgeTool,
)
from agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

# Rough token estimation: 1 token ≈ 4 chars for English text
TOKEN_ESTIMATE_RATIO = 4
# Target: leave ~2000 tokens for the LLM response within an 8K context
MAX_PROMPT_TOKENS = 6000
# Hard cap on history messages regardless of size
MAX_HISTORY_MESSAGES = 20


class LLMError(Exception):
    pass


class RestaurantAgent:
    def __init__(self) -> None:
        self.tools = self._build_tools()
        self.llm = LLMClient()
        self.planner = LocalPlanner()
        self.react = ReActLoop(self.llm, self.tools)
        self.order_workflow = OrderWorkflow(self)
        self.reservation_workflow = ReservationWorkflow(self)
        self.memory_manager = MemoryManager()
        self.memory_engine = MemoryEngine(self.memory_manager)

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

        try:
            await sync_to_async(self.memory_manager.record_user_message)(
                customer_id=customer_id,
                conversation_id=conversation_id,
                message=message,
            )
        except Exception:
            logger.debug("Failed to record episodic event", exc_info=True)

        # Try reservation workflow first (before order workflow)
        # because reservation keywords ("table", "book") may overlap with order intent
        workflow_response_reservation = await self.reservation_workflow.handle(message, memory)
        if workflow_response_reservation:
            memory.remember_message(workflow_response_reservation)
            return workflow_response_reservation

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
            except LLMError:
                logger.warning("LLM call failed, falling back to local planner")
                response = await self._run_locally(message, memory)
            except Exception:
                logger.exception("Unexpected error in ReAct loop, falling back to local planner")
                response = await self._run_locally(message, memory)
        else:
            response = await self._run_locally(message, memory)

        memory.remember_message(response)

        try:
            await sync_to_async(self.memory_manager.record_assistant_response)(
                customer_id=customer_id,
                conversation_id=conversation_id,
                response=response,
            )
            if customer_id:
                await sync_to_async(self.memory_manager.extract_and_learn)(
                    customer_id=customer_id,
                    conversation_id=conversation_id,
                    working_memory=memory,
                )
                await sync_to_async(self.memory_manager.update_profile)(customer_id=customer_id)

                # Run conversation summarization for fact extraction
                try:
                    user_msgs = [m["content"] for m in (history or []) if m.get("role") == "user"]
                    user_msgs.append(message)  # include the current message
                    assistant_msgs = [m["content"] for m in (history or []) if m.get("role") == "assistant"]
                    tool_calls_data = [
                        {"name": r.get("tool_name", ""), "success": r.get("success", False)}
                        for r in getattr(memory, "tool_results", []) or []
                    ]
                    await persist_summary(
                        self.memory_manager,
                        customer_id=customer_id,
                        conversation_id=conversation_id,
                        user_messages=user_msgs,
                        assistant_messages=assistant_msgs,
                        tool_calls=tool_calls_data,
                    )
                except Exception:
                    logger.debug("Conversation summarization failed", exc_info=True)
        except Exception:
            logger.debug("Failed to record episodic/semantic events", exc_info=True)

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
        if not message.strip():
            raise ValueError("Message cannot be empty.")

        memory = memory or ConversationMemory.from_history(history)
        memory.remember_user_message(message)

        try:
            await sync_to_async(self.memory_manager.record_user_message)(
                customer_id=customer_id,
                conversation_id=conversation_id,
                message=message,
            )
        except Exception:
            logger.debug("Failed to record episodic event", exc_info=True)

        # Try reservation workflow first (before order workflow)
        workflow_response_reservation = await self.reservation_workflow.handle(message, memory)
        if workflow_response_reservation:
            memory.remember_message(workflow_response_reservation)
            yield {"type": "token", "content": workflow_response_reservation}
            yield {"type": "done", "response": workflow_response_reservation, "steps": 0}
            return

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
            except LLMError:
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

        # Inject proactive memory suggestions for returning guests
        try:
            suggestions = await get_suggestions(self.memory_engine, customer_id)
            if suggestions.get("welcome_back_context"):
                greeting_context = await get_greeting(self.memory_engine, customer_id)
                if greeting_context:
                    memory_context += f"\n\nCustomer memory (for personalization): {greeting_context}"
            # Add discussed topics
            if memory.discussed_topics:
                memory_context += f"\nTopics discussed this conversation: {', '.join(memory.discussed_topics)}"
            if memory.conversation_summary:
                memory_context += f"\nConversation note: {memory.conversation_summary}"
        except Exception:
            logger.debug("Failed to inject memory suggestions", exc_info=True)

        try:
            long_term = self.memory_manager.build_context_string(customer_id=customer_id)
            if long_term:
                memory_context += f"\n{long_term}"
        except Exception:
            logger.debug("Failed to load long-term memory context", exc_info=True)

        rag_context = await self._retrieve_rag_context(message)

        system_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt()},
            {"role": "system", "content": memory_context},
        ]
        if rag_context:
            system_messages.append({"role": "system", "content": rag_context})
        # Smarter history truncation: fit within token budget
        system_messages.extend(self._select_history(history))

        try:
            self.react.set_tool_trace_callback(
                lambda name, args, result, duration_ms=None: self._trace_tool(
                    name, args, result, duration_ms=duration_ms,
                    customer_id=customer_id,
                    conversation_id=conversation_id,
                )
            )
            result = await self.react.run(system_messages, message, memory)
        finally:
            self.react.set_tool_trace_callback(None)

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
        memory_context = f"Conversation memory: {memory.as_context()}"

        # Inject proactive memory suggestions for returning guests
        try:
            suggestions = await get_suggestions(self.memory_engine, customer_id)
            if suggestions.get("welcome_back_context"):
                greeting_context = await get_greeting(self.memory_engine, customer_id)
                if greeting_context:
                    memory_context += f"\n\nCustomer memory (for personalization): {greeting_context}"
            if memory.discussed_topics:
                memory_context += f"\nTopics discussed this conversation: {', '.join(memory.discussed_topics)}"
            if memory.conversation_summary:
                memory_context += f"\nConversation note: {memory.conversation_summary}"
        except Exception:
            logger.debug("Failed to inject memory suggestions", exc_info=True)

        try:
            long_term = self.memory_manager.build_context_string(customer_id=customer_id)
            if long_term:
                memory_context += f"\n{long_term}"
        except Exception:
            logger.debug("Failed to load long-term memory context", exc_info=True)

        rag_context = await self._retrieve_rag_context(message)

        system_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt()},
            {"role": "system", "content": memory_context},
        ]
        if rag_context:
            system_messages.append({"role": "system", "content": rag_context})
        # Smarter history truncation: fit within token budget
        system_messages.extend(self._select_history(history))

        final_response = ""
        final_goals: list[dict[str, str]] = []

        try:
            self.react.set_tool_trace_callback(
                lambda name, args, result, duration_ms=None: self._trace_tool(
                    name, args, result, duration_ms=duration_ms,
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
        name: str,
        args: dict[str, Any],
        result: ToolResult,
        duration_ms: int | None = None,
        *,
        customer_id: str | None = None,
        conversation_id: str | None = None,
    ) -> None:
        try:
            self.memory_manager.record_tool_event(
                customer_id=customer_id,
                conversation_id=conversation_id,
                tool_name=name,
                tool_args=args,
                result=result,
                duration_ms=duration_ms,
            )
        except Exception:
            logger.debug("Failed to trace tool event", exc_info=True)

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
        result = await sync_to_async(tool.execute)(**args)
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
        tools = [
            MenuTool(),
            GetMenuItemDetailsTool(),
            ManageCartTool(),
            CheckoutCartTool(),
            FAQTool(),
            ReservationTool(),
            OrderTool(),
            BillingTool(),
            PaymentTool(),
            RecommendMenuTool(),
            ManagePreferencesTool(),
            EscalationTool(),
            SearchKnowledgeTool(),
        ]
        return {tool.name: tool for tool in tools}

    @staticmethod
    def _select_history(history: list[dict]) -> list[dict]:
        """Smart history truncation: keep as many recent messages as fit in the token budget.

        Prioritizes the most recent messages. Drops oldest first when over budget.
        System prompts (role="system") and tool results with important data are preserved
        over plain assistant responses when trimming.
        """
        if not history:
            return []

        selected: list[dict] = []
        token_count = 0

        # Walk from the most recent message backwards
        for msg in reversed(history):
            content = msg.get("content", "") or ""
            # Estimate tokens: ~4 chars per token, plus overhead per message
            msg_tokens = len(str(content)) // TOKEN_ESTIMATE_RATIO + 2

            if token_count + msg_tokens > MAX_PROMPT_TOKENS:
                # If this is the very first (most recent) message, keep a truncated version
                if not selected:
                    truncated = str(content)[:MAX_PROMPT_TOKENS * TOKEN_ESTIMATE_RATIO // 2]
                    kept = dict(msg)
                    kept["content"] = truncated + "..."
                    selected.insert(0, kept)
                break

            token_count += msg_tokens
            selected.insert(0, msg)

        logger.info(
            "History truncation: %d messages → %d messages (~%d estimated tokens)",
            len(history), len(selected), token_count,
        )
        return selected

    async def _retrieve_rag_context(self, message: str) -> str:
        """Auto-retrieve relevant knowledge for the user's message."""
        try:
            results = await sync_to_async(search_knowledge)(message, top_k=3)
            return format_knowledge_context(results)
        except Exception:
            logger.debug("RAG retrieval failed", exc_info=True)
            return ""


agent = RestaurantAgent()
