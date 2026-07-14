from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from agent.memory import ConversationMemory
from agent.models import EpisodicMemory, CustomerProfile, SemanticMemory

if TYPE_CHECKING:
    from agent.tools.base import ToolResult

logger = logging.getLogger(__name__)

CONFIDENCE_INCREMENT = 0.1
MAX_CONFIDENCE = 1.0
INITIAL_CONFIDENCE = 0.5

SEMANTIC_CATEGORIES = {
    "preference": "preference",
    "dietary": "dietary",
    "favorite": "favorite",
    "dislike": "dislike",
    "budget": "budget",
    "spice": "spice",
    "cuisine": "cuisine",
    "pattern": "pattern",
}


@dataclass
class MemorySnapshot:
    episodic_summary: str
    semantic_facts: str
    profile_summary: str
    working_memory: str


class MemoryManager:
    def __init__(self) -> None:
        pass

    def record_tool_event(
        self,
        *,
        customer_id: str | None,
        conversation_id: str | None,
        tool_name: str,
        tool_args: dict[str, Any],
        result: ToolResult,
        duration_ms: int | None = None,
        goal_description: str | None = None,
        goal_status: str | None = None,
    ) -> None:
        event = EpisodicMemory(
            customer_id=customer_id,
            conversation_id=conversation_id,
            event_type="tool_call",
            event_data=json.dumps(tool_args, default=str),
            tool_name=tool_name,
            tool_success=result.success,
            tool_duration_ms=duration_ms,
            goal_description=goal_description,
            goal_status=goal_status,
            outcome="success" if result.success else "failure",
        )
        event.save()

    def record_user_message(
        self,
        *,
        customer_id: str | None,
        conversation_id: str | None,
        message: str,
    ) -> None:
        event = EpisodicMemory(
            customer_id=customer_id,
            conversation_id=conversation_id,
            event_type="user_message",
            user_message=message,
            outcome="received",
        )
        event.save()

    def record_assistant_response(
        self,
        *,
        customer_id: str | None,
        conversation_id: str | None,
        response: str,
    ) -> None:
        event = EpisodicMemory(
            customer_id=customer_id,
            conversation_id=conversation_id,
            event_type="assistant_response",
            assistant_response=response,
            outcome="delivered",
        )
        event.save()

    def record_goal_completion(
        self,
        *,
        customer_id: str | None,
        conversation_id: str | None,
        goal_description: str,
        goal_status: str,
    ) -> None:
        event = EpisodicMemory(
            customer_id=customer_id,
            conversation_id=conversation_id,
            event_type="goal_completed",
            goal_description=goal_description,
            goal_status=goal_status,
            outcome=goal_status,
        )
        event.save()

    def learn_fact(
        self,
        *,
        customer_id: str,
        category: str,
        fact_key: str,
        fact_value: str,
        conversation_id: str | None = None,
        source_tool: str | None = None,
    ) -> None:
        if not customer_id:
            return

        category = SEMANTIC_CATEGORIES.get(category, "pattern")
        now = datetime.now(timezone.utc)

        existing = SemanticMemory.objects.filter(
            customer_id=customer_id,
            category=category,
            fact_key=fact_key,
        ).first()

        if existing:
            if existing.fact_value != fact_value:
                existing.fact_value = fact_value
                existing.confidence = min(existing.confidence + CONFIDENCE_INCREMENT, MAX_CONFIDENCE)
            else:
                existing.confidence = min(existing.confidence + CONFIDENCE_INCREMENT * 0.5, MAX_CONFIDENCE)
            existing.observation_count += 1
            existing.last_observed_at = now
            existing.save()
            logger.info(
                "Semantic fact updated: customer=%s key=%s confidence=%.2f",
                customer_id,
                fact_key,
                existing.confidence,
            )
        else:
            fact = SemanticMemory(
                customer_id=customer_id,
                category=category,
                fact_key=fact_key,
                fact_value=fact_value,
                confidence=INITIAL_CONFIDENCE,
                observation_count=1,
                source_conversation_id=conversation_id,
                source_tool=source_tool,
                created_at=now,
                last_observed_at=now,
            )
            fact.save()
            logger.info(
                "New semantic fact learned: customer=%s key=%s value=%s",
                customer_id,
                fact_key,
                fact_value,
            )

    def extract_and_learn(
        self,
        *,
        customer_id: str | None,
        conversation_id: str | None,
        working_memory: ConversationMemory,
    ) -> None:
        if not customer_id:
            return

        if working_memory.customer_name:
            self.learn_fact(
                customer_id=customer_id,
                category="preference",
                fact_key="name",
                fact_value=working_memory.customer_name,
                conversation_id=conversation_id,
            )

        if working_memory.email:
            self.learn_fact(
                customer_id=customer_id,
                category="preference",
                fact_key="email",
                fact_value=working_memory.email,
                conversation_id=conversation_id,
            )

        if working_memory.phone:
            self.learn_fact(
                customer_id=customer_id,
                category="preference",
                fact_key="phone",
                fact_value=working_memory.phone,
                conversation_id=conversation_id,
            )

        if working_memory.party_size:
            self.learn_fact(
                customer_id=customer_id,
                category="pattern",
                fact_key="typical_party_size",
                fact_value=str(working_memory.party_size),
                conversation_id=conversation_id,
            )

        self._extract_facts_from_tool_results(
            customer_id=customer_id,
            conversation_id=conversation_id,
            working_memory=working_memory,
        )

    def _extract_facts_from_tool_results(
        self,
        *,
        customer_id: str,
        conversation_id: str | None,
        working_memory: ConversationMemory,
    ) -> None:
        for result in working_memory.tool_results:
            if not result.get("success") or not result.get("data"):
                continue
            memory_updates = result.get("memory_updates", {})
            tool_name = result.get("tool_name", "")
            for key, value in memory_updates.items():
                if value is None:
                    continue
                self._classify_and_learn(
                    customer_id=customer_id,
                    conversation_id=conversation_id,
                    key=key,
                    value=str(value),
                    tool_name=tool_name,
                )

    def _classify_and_learn(
        self,
        *,
        customer_id: str,
        conversation_id: str | None,
        key: str,
        value: str,
        tool_name: str,
    ) -> None:
        if not value or value in ("None", "null", ""):
            return

        if key == "payment_method":
            self.learn_fact(
                customer_id=customer_id,
                category="preference",
                fact_key="preferred_payment",
                fact_value=value,
                conversation_id=conversation_id,
                source_tool=tool_name,
            )
        elif key == "delivery_method":
            self.learn_fact(
                customer_id=customer_id,
                category="preference",
                fact_key="preferred_delivery",
                fact_value=value,
                conversation_id=conversation_id,
                source_tool=tool_name,
            )
        elif key == "party_size":
            self.learn_fact(
                customer_id=customer_id,
                category="pattern",
                fact_key="typical_party_size",
                fact_value=value,
                conversation_id=conversation_id,
                source_tool=tool_name,
            )
        elif key == "reservation_date":
            self.learn_fact(
                customer_id=customer_id,
                category="pattern",
                fact_key="last_reservation_date",
                fact_value=value,
                conversation_id=conversation_id,
                source_tool=tool_name,
            )
        elif key == "reservation_time":
            self.learn_fact(
                customer_id=customer_id,
                category="pattern",
                fact_key="preferred_time",
                fact_value=value,
                conversation_id=conversation_id,
                source_tool=tool_name,
            )
        elif key == "order_status" and value == "paid":
            self.learn_fact(
                customer_id=customer_id,
                category="pattern",
                fact_key="has_ordered",
                fact_value="true",
                conversation_id=conversation_id,
                source_tool=tool_name,
            )

    def update_profile(
        self,
        *,
        customer_id: str,
    ) -> CustomerProfile | None:
        if not customer_id:
            return None

        profile = CustomerProfile.objects.filter(
            customer_id=customer_id,
        ).first()

        if not profile:
            profile = CustomerProfile(customer_id=customer_id)
            profile.save()

        facts = SemanticMemory.objects.filter(
            customer_id=customer_id,
            confidence__gte=0.4,
        )

        for fact in facts:
            if fact.category == "preference" and fact.fact_key == "name":
                profile.display_name = fact.fact_value
            elif fact.category == "cuisine":
                profile.preferred_cuisine = fact.fact_value
            elif fact.category == "dietary":
                profile.dietary_restrictions = fact.fact_value
            elif fact.category == "spice":
                profile.spice_tolerance = fact.fact_value
            elif fact.category == "budget":
                profile.budget_range = fact.fact_value
            elif fact.category == "favorite":
                existing = profile.favorite_items or ""
                items = [i.strip() for i in existing.split(",") if i.strip()]
                if fact.fact_value not in items:
                    items.append(fact.fact_value)
                profile.favorite_items = ", ".join(items[-10:])

        profile.save()
        return profile

    def get_episodic_history(
        self,
        *,
        customer_id: str,
        limit: int = 20,
    ) -> list[dict]:
        events = list(
            EpisodicMemory.objects.filter(customer_id=customer_id)
            .order_by("-created_at")[:limit]
        )
        return [e.to_dict() for e in reversed(events)]

    def get_semantic_facts(
        self,
        *,
        customer_id: str,
    ) -> list[dict]:
        facts = list(
            SemanticMemory.objects.filter(
                customer_id=customer_id,
                confidence__gte=0.3,
            ).order_by("-confidence")
        )
        return [f.to_dict() for f in facts]

    def get_profile(
        self,
        *,
        customer_id: str,
    ) -> CustomerProfile | None:
        return CustomerProfile.objects.filter(customer_id=customer_id).first()

    def build_context_string(
        self,
        *,
        customer_id: str | None,
        limit_facts: int = 10,
    ) -> str:
        if not customer_id:
            return ""

        facts = self.get_semantic_facts(customer_id=customer_id)
        if not facts:
            return ""

        lines = [f"- {f['category']}: {f['fact_key']} = {f['fact_value']} (confidence: {f['confidence']})" for f in facts[:limit_facts]]
        return "Known facts about this customer:\n" + "\n".join(lines)

    def build_snapshot(
        self,
        *,
        customer_id: str | None,
        conversation_id: str | None,
        working_memory: ConversationMemory,
    ) -> MemorySnapshot:
        episodic_summary = ""
        if customer_id:
            recent = self.get_episodic_history(customer_id=customer_id, limit=5)
            if recent:
                events = [f"{e['event_type']}: {e.get('tool_name', '-')}" for e in recent]
                episodic_summary = "Recent events: " + " → ".join(events)

        semantic_facts = ""
        if customer_id:
            semantic_facts = self.build_context_string(customer_id=customer_id)

        profile_summary = ""
        if customer_id:
            profile = self.get_profile(customer_id=customer_id)
            if profile:
                parts = []
                if profile.display_name:
                    parts.append(f"name={profile.display_name}")
                if profile.preferred_cuisine:
                    parts.append(f"cuisine={profile.preferred_cuisine}")
                if profile.dietary_restrictions:
                    parts.append(f"dietary={profile.dietary_restrictions}")
                if profile.total_orders:
                    parts.append(f"orders={profile.total_orders}")
                profile_summary = ", ".join(parts)

        working = working_memory.as_context()

        return MemorySnapshot(
            episodic_summary=episodic_summary,
            semantic_facts=semantic_facts,
            profile_summary=profile_summary,
            working_memory=working,
        )
