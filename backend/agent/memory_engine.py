"""Memory Engine — real-time customer memory orchestration.

Extends the passive MemoryManager with active capabilities:
- Real-time inline preference extraction during conversation
- Usual-order detection from order history
- Proactive suggestion data generation
- Personalized greeting context

This module is called from the agent controller on every user message.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

from asgiref.sync import sync_to_async
from django.db.models import Count

if TYPE_CHECKING:
    from agent.memory import ConversationMemory
    from agent.memory_manager import MemoryManager

logger = logging.getLogger(__name__)

# ── Inline extraction patterns ──────────────────────────────────────────

# "my favorite is X", "X is my favorite"
FAVORITE_PATTERN = re.compile(
    r"(?:my\s+favou?rite\s+(?:is|dish\s+is|food\s+is|drink\s+is|item\s+is)\s+([A-Za-z\s]+?))"
    r"(?:\s*(?:\.|,|!|\?|and|please|thanks|$))",
    re.IGNORECASE,
)
FAVORITE_ALT_PATTERN = re.compile(
    r"([A-Za-z\s]+?)\s+is\s+(?:my\s+favou?rite)",
    re.IGNORECASE,
)

# "I love X", "I like X", "I really enjoy X"
LIKE_PATTERN = re.compile(
    r"(?:i\s+(?:really\s+|absolutely\s+)?(?:love|like|enjoy)\s+([A-Za-z\s]+?))"
    r"(?:\s*(?:\.|,|!|\?|and|please|thanks|$))",
    re.IGNORECASE,
)

# "I don't like X", "I hate X", "I can't stand X"
DISLIKE_PATTERN = re.compile(
    r"(?:i\s+(?:don'?t\s+like|hate|can'?t\s+stand|dislike|not\s+(?:a\s+)?fan\s+of)\s+([A-Za-z\s]+?))"
    r"(?:\s*(?:\.|,|!|\?|and|please|thanks|$))",
    re.IGNORECASE,
)

# "the usual", "the usual please", "I'll have the usual"
USUAL_PATTERN = re.compile(
    r"\bthe\s+usual\b",
    re.IGNORECASE,
)

# "I usually order X", "I always get X"
USUAL_ORDER_PATTERN = re.compile(
    r"(?:i\s+(?:usually|always|normally|typically)\s+(?:order|get|have)\s+([A-Za-z\s]+?))"
    r"(?:\s*(?:\.|,|!|\?|and|please|thanks|$))",
    re.IGNORECASE,
)

# Dietary/allergy indicators
DIETARY_PATTERN = re.compile(
    r"(?:i'?m\s+|i\s+am\s+)(allergic\s+to\s+[A-Za-z\s,]+?)(?:\.|,|!|\?|$)",
    re.IGNORECASE,
)

# Spice preference
SPICE_PATTERN = re.compile(
    r"(?:i\s+(?:love|like|prefer|enjoy|want)\s+).{0,20}?(spicy|mild|hot|not\s+spicy)",
    re.IGNORECASE,
)


def _extract_favorite(message: str) -> str | None:
    """Extract 'my favorite is X' from a message."""
    match = FAVORITE_PATTERN.search(message)
    if match:
        return match.group(1).strip()
    match = FAVORITE_ALT_PATTERN.search(message)
    if match:
        return match.group(1).strip()
    return None


def _extract_like(message: str) -> str | None:
    """Extract 'I love/like X' from a message."""
    match = LIKE_PATTERN.search(message)
    if match:
        return match.group(1).strip()
    return None


def _extract_dislike(message: str) -> str | None:
    """Extract 'I don't like X' from a message."""
    match = DISLIKE_PATTERN.search(message)
    if match:
        return match.group(1).strip()
    return None


def _extract_usual_indicator(message: str) -> bool:
    """Check if user said 'the usual'."""
    return bool(USUAL_PATTERN.search(message))


def _extract_usual_order_pattern(message: str) -> str | None:
    """Extract 'I usually order X' from a message."""
    match = USUAL_ORDER_PATTERN.search(message)
    if match:
        return match.group(1).strip()
    return None


def _extract_dietary(message: str) -> str | None:
    """Extract 'I'm allergic to X' from a message."""
    match = DIETARY_PATTERN.search(message)
    if match:
        return match.group(1).strip().lower()
    return None


def _extract_spice(message: str) -> str | None:
    """Extract spice preference from a message."""
    match = SPICE_PATTERN.search(message)
    if match:
        return match.group(1).strip().lower()
    return None


def _infer_topic(message: str) -> str | None:
    """Infer the conversation topic from a message."""
    text = message.lower()
    topics: list[tuple[str, str]] = [
        ("ordering", r"\b(order|i['’]?d like|i want|add|remove|cart|checkout|menu item)\b"),
        ("menu", r"\b(menu|recommend|suggest|what.*(?:have|serve|offer)|do you have)\b"),
        ("reservation", r"\b(table|reservation|book|reserve|seat)\b"),
        ("payment", r"\b(pay|payment|card|cash|chapa|telebirr|bill|check)\b"),
        ("preference", r"\b(favorite|favourite|love|like|prefer|usual|allergic|dietary)\b"),
        ("info", r"\b(hour|address|parking|wifi|open|close|phone|contact)\b"),
        ("complaint", r"\b(complaint|issue|problem|wrong|mistake|refund|dissatisfied)\b"),
    ]
    for topic, pattern in topics:
        if re.search(pattern, text):
            return topic
    return None


class MemoryEngine:
    """Active memory orchestration engine.

    Provides real-time preference extraction and proactive suggestion
    data that other components (controller, prompts, LLM) consume.
    """

    def __init__(self, memory_manager: MemoryManager) -> None:
        self.memory_manager = memory_manager

    # ── Real-time inline extraction ───────────────────────────────────────

    def extract_inline(self, message: str, *, customer_id: str | None, memory: ConversationMemory) -> dict[str, Any]:
        """Extract preferences from a single message and persist them.

        Called on every user message during the conversation (not just at end).
        Returns a dict of what was extracted for potential use by the controller.

        Args:
            message: The user's message text.
            customer_id: The customer's ID (may be None for anonymous).
            memory: The current ConversationMemory for topic tracking.

        Returns:
            Dict with keys: favorite, like, dislike, usual, dietary, spice, topic
            Values are the extracted strings or None.
        """
        extracted: dict[str, Any] = {
            "favorite": None,
            "like": None,
            "dislike": None,
            "usual_indicator": False,
            "usual_order": None,
            "dietary": None,
            "spice": None,
            "topic": _infer_topic(message) or memory.order_status or None,
        }

        # ── Run all extraction functions (runs even for anonymous users) ──
        favorite = _extract_favorite(message)
        if favorite:
            extracted["favorite"] = favorite

        like = _extract_like(message)
        if like:
            extracted["like"] = like

        dislike = _extract_dislike(message)
        if dislike:
            extracted["dislike"] = dislike

        if _extract_usual_indicator(message):
            extracted["usual_indicator"] = True

        usual_order = _extract_usual_order_pattern(message)
        if usual_order:
            extracted["usual_order"] = usual_order

        dietary = _extract_dietary(message)
        if dietary:
            extracted["dietary"] = dietary

        spice = _extract_spice(message)
        if spice:
            extracted["spice"] = spice

        # Track conversation topic
        topic = extracted["topic"]
        if topic:
            if topic not in memory.discussed_topics:
                memory.discussed_topics.append(topic)

        # If no customer_id, extract values but don't persist
        if not customer_id:
            return extracted

        # ── Persist extracted facts ───────────────────────────────────────
        if favorite:
            self.memory_manager.learn_fact(
                customer_id=customer_id,
                category="favorite",
                fact_key=f"favorite_{favorite.lower().replace(' ', '_')}",
                fact_value=favorite,
            )
            logger.info("Inline extracted favorite: %s for customer=%s", favorite, customer_id)

        if like:
            self.memory_manager.learn_fact(
                customer_id=customer_id,
                category="preference",
                fact_key=f"likes_{like.lower().replace(' ', '_')}",
                fact_value=like,
            )
            logger.info("Inline extracted like: %s for customer=%s", like, customer_id)

        if dislike:
            self.memory_manager.learn_fact(
                customer_id=customer_id,
                category="dislike",
                fact_key=f"dislikes_{dislike.lower().replace(' ', '_')}",
                fact_value=dislike,
            )
            logger.info("Inline extracted dislike: %s for customer=%s", dislike, customer_id)

        # ── "The usual" detection ──────────────────────────────────────────
        if extracted["usual_indicator"]:
            usual = self.get_usual_order(customer_id)
            if usual:
                extracted["usual_order"] = usual["item_name"]

        # ── "I usually order X" pattern ────────────────────────────────────
        if usual_order:
            self.memory_manager.learn_fact(
                customer_id=customer_id,
                category="pattern",
                fact_key="usual_order",
                fact_value=usual_order,
            )

        # ── Dietary extraction ─────────────────────────────────────────────
        if dietary:
            self.memory_manager.learn_fact(
                customer_id=customer_id,
                category="dietary",
                fact_key=f"dietary_{dietary[:40].replace(' ', '_')}",
                fact_value=dietary,
            )

        # ── Spice extraction ───────────────────────────────────────────────
        if spice:
            self.memory_manager.learn_fact(
                customer_id=customer_id,
                category="spice",
                fact_key="spice_tolerance",
                fact_value=spice,
            )

        # Update profile after any extraction
        if any(v is not None for v in [extracted["favorite"], extracted["like"],
                                        extracted["dislike"], extracted["dietary"],
                                        extracted["spice"], extracted["usual_order"]]):
            self.memory_manager.update_profile(customer_id=customer_id)

        return extracted

    # ── Usual-order detection ─────────────────────────────────────────────

    def get_usual_order(self, customer_id: str) -> dict[str, Any] | None:
        """Find the customer's most commonly ordered item from order history.

        Queries completed/paid orders and finds the most frequently ordered item.

        Args:
            customer_id: The customer's ID.

        Returns:
            Dict with item_name, order_count, last_ordered or None if no history.
        """
        if not customer_id:
            return None

        try:
            from orders.models import Order, OrderItem

            paid_orders = Order.objects.filter(
                customer_id=customer_id,
                status="paid",
            ).order_by("-created_at")

            if not paid_orders.exists():
                return None

            # Count item frequency across all paid orders
            item_counts = (
                OrderItem.objects.filter(order__in=paid_orders)
                .values("item_name")
                .annotate(count=Count("id"))
                .order_by("-count")
            )

            if not item_counts:
                return None

            most_ordered = item_counts[0]
            last_order = paid_orders.first()

            return {
                "item_name": most_ordered["item_name"],
                "order_count": most_ordered["count"],
                "last_ordered": last_order.created_at.isoformat() if last_order else None,
            }
        except Exception:
            logger.debug("Failed to detect usual order", exc_info=True)
            return None

    # ── Proactive suggestion data ─────────────────────────────────────────

    def get_proactive_suggestions(self, customer_id: str | None) -> dict[str, Any]:
        """Generate data for proactive agent suggestions.

        Returns structured dict that can be injected into the system prompt
        so the LLM can make personalized suggestions.

        Args:
            customer_id: The customer's ID (may be None).

        Returns:
            Dict with keys:
            - has_history: bool
            - usual_order: str or None
            - favorite_items: list[str]
            - preferences: list[str]
            - welcome_back_context: str for prompt injection
        """
        result: dict[str, Any] = {
            "has_history": False,
            "usual_order": None,
            "favorite_items": [],
            "preferences": [],
            "welcome_back_context": "",
        }

        if not customer_id:
            return result

        try:
            # Get profile
            profile = self.memory_manager.get_profile(customer_id=customer_id)
            if not profile:
                return result

            result["has_history"] = True

            # Favorites from profile
            if profile.favorite_items:
                result["favorite_items"] = [
                    i.strip() for i in profile.favorite_items.split(",") if i.strip()
                ]

            # Dietary info
            prefs = []
            if profile.dietary_restrictions:
                prefs.append(f"dietary: {profile.dietary_restrictions}")
            if profile.preferred_cuisine:
                prefs.append(f"cuisine: {profile.preferred_cuisine}")
            if profile.spice_tolerance:
                prefs.append(f"spice: {profile.spice_tolerance}")
            if profile.budget_range:
                prefs.append(f"budget: {profile.budget_range}")
            result["preferences"] = prefs

            # Usual order from semantic memory or order history
            facts = self.memory_manager.get_semantic_facts(customer_id=customer_id)
            usual_fact = next(
                (f for f in facts if f.get("fact_key") == "usual_order"),
                None,
            )
            if usual_fact:
                result["usual_order"] = usual_fact["fact_value"]
            else:
                # Fall back to order history analysis
                usual = self.get_usual_order(customer_id)
                if usual:
                    result["usual_order"] = usual["item_name"]

            # Build welcome-back context string
            parts = []
            if profile.display_name:
                parts.append(f"name={profile.display_name}")
            if result["usual_order"]:
                parts.append(f"usual={result['usual_order']}")
            if profile.total_orders:
                parts.append(f"total_orders={profile.total_orders}")
            if result["favorite_items"]:
                parts.append(f"favorites={', '.join(result['favorite_items'][:3])}")
            if prefs:
                parts.append("; ".join(prefs[:3]))

            if parts:
                result["welcome_back_context"] = " | ".join(parts)

        except Exception:
            logger.debug("Failed to build proactive suggestions", exc_info=True)

        return result

    # ── Personalized greeting data ────────────────────────────────────────

    def get_personalized_greeting(self, customer_id: str | None) -> str:
        """Generate a short context string for the LLM's greeting.

        Returns a plain-text string that can be injected into the system
        prompt to help the agent generate a personalized greeting.
        """
        suggestions = self.get_proactive_suggestions(customer_id)
        if not suggestions["has_history"]:
            return ""

        parts = []
        name = None
        if suggestions["welcome_back_context"]:
            import re as _re
            name_match = _re.search(r"name=([^|\s]+)", suggestions["welcome_back_context"])
            if name_match:
                name = name_match.group(1)
                parts.append(f"Welcome back, {name}!")

        if suggestions["usual_order"]:
            if name:
                parts.append(f"Would {name} like their usual {suggestions['usual_order']}?")
            else:
                parts.append(f"Customer's usual order is {suggestions['usual_order']}.")

        if suggestions["favorite_items"]:
            favs = ", ".join(suggestions["favorite_items"][:2])
            parts.append(f"Favorites include: {favs}.")

        profile = self.memory_manager.get_profile(customer_id=customer_id) if customer_id else None
        if profile and profile.dietary_restrictions:
            parts.append(f"Dietary: {profile.dietary_restrictions}.")

        return " ".join(parts) if parts else ""


# ── Async wrappers for use in async controller methods ──────────────────


async def inline_extract(
    engine: MemoryEngine,
    message: str,
    *,
    customer_id: str | None,
    memory: ConversationMemory,
) -> dict[str, Any]:
    """Async wrapper around MemoryEngine.extract_inline."""
    return await sync_to_async(engine.extract_inline)(
        message,
        customer_id=customer_id,
        memory=memory,
    )


async def get_suggestions(
    engine: MemoryEngine,
    customer_id: str | None,
) -> dict[str, Any]:
    """Async wrapper around MemoryEngine.get_proactive_suggestions."""
    return await sync_to_async(engine.get_proactive_suggestions)(customer_id)


async def get_greeting(
    engine: MemoryEngine,
    customer_id: str | None,
) -> str:
    """Async wrapper around MemoryEngine.get_personalized_greeting."""
    return await sync_to_async(engine.get_personalized_greeting)(customer_id)
