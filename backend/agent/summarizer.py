"""Conversation summarization and fact extraction engine.

This module sits between the agent controller and the memory manager.
After each turn (or at conversation end), the summarizer scans session
messages, extracts durable facts about the customer, and writes them
into SemanticMemory and CustomerProfile.

Design:
- The summarizer is **rule-based** (no extra LLM call) to keep costs low.
- It uses regex patterns to extract names, emails, phones, food preferences,
  ordering patterns, and reservation details.
- Extracted facts are written to SemanticMemory via MemoryManager.learn_fact().
- A short summary text is stored in the session's metadata["summary"] field.
- Confidence is tracked — facts seen multiple times gain higher confidence.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)

# ── Patterns ──────────────────────────────────────────────────────────

NAME_PATTERN = re.compile(
    r"(?:my name is|i'?m\s+called|call me|this is|i am|i'm)\s+"
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    re.IGNORECASE,
)

EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
)

PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}",
)

PREFERENCE_PATTERN = re.compile(
    r"(?:i\s+(?:love|like|enjoy|prefer|would like|want)\s+)\s*"
    r"([A-Za-z\s]+?)(?:\s*(?:please|thanks|,|\.|$))",
    re.IGNORECASE,
)

DIETARY_PATTERN = re.compile(
    r"(?:i'?m\s+|i\s+am\s+)(?:allergic\s+to|vegan|vegetarian|gluten-free|"
    r"lactose[- ]intolerant|dairy[- ]free|nut[- ]allergic|"
    r"halal|kosher)(?:.*?)(?:\.|,|$)",
    re.IGNORECASE,
)

DISLIKE_PATTERN = re.compile(
    r"(?:i\s+(?:don'?t\s+like|hate|can'?t\s+stand|dislike|not\s+a\s+fan\s+of)\s+)\s*"
    r"([A-Za-z\s]+?)(?:\s*(?:please|thanks|,|\.|$))",
    re.IGNORECASE,
)

SPICE_PATTERN = re.compile(
    r"(?:spicy|mild|hot|not\s+spicy|extra\s+spicy|medium\s+spicy)",
    re.IGNORECASE,
)

ORDER_PATTERN = re.compile(
    r"(?:i'?d\s+like\s+to\s+order|i\s+want\s+to\s+order|can\s+i\s+get|"
    r"can\s+i\s+have|i\s+will\s+have|i\s+want)\s+([A-Za-z\s]+?)(?:\s*(?:please|thanks|,|\.|$))",
    re.IGNORECASE,
)

DELIVERY_PATTERN = re.compile(
    r"(?:delivery|takeaway|pickup|dine[- ]in|eat[- ]in)",
    re.IGNORECASE,
)

BUDGET_PATTERN = re.compile(
    r"(?:budget|spend|cost|price|cheap|affordable|expensive)\s*(?:is|around|under|of)?\s*"
    r"(\d+[\d\.,]*(?:\s*(?:birr|dollar|usd|etb|bírr))?)",
    re.IGNORECASE,
)

CUISINE_PATTERN = re.compile(
    r"(?:ethiopian|italian|mexican|chinese|japanese|indian|american|"
    r"french|thai|korean|mediterranean|middle\s+eastern)",
    re.IGNORECASE,
)


# ── Extractor functions ───────────────────────────────────────────────


def _extract_name(user_messages: list[str]) -> str | None:
    """Extract the customer's name from user messages."""
    for msg in user_messages:
        match = NAME_PATTERN.search(msg)
        if match:
            return match.group(1).strip()
    return None


def _extract_email(user_messages: list[str]) -> str | None:
    """Extract email address from user messages."""
    for msg in user_messages:
        match = EMAIL_PATTERN.search(msg)
        if match:
            return match.group(0).strip()
    return None


def _extract_phone(user_messages: list[str]) -> str | None:
    """Extract phone number from user messages."""
    for msg in user_messages:
        match = PHONE_PATTERN.search(msg)
        if match:
            return match.group(0).strip()
    return None


def _extract_preferences(user_messages: list[str]) -> list[str]:
    """Extract food/drink preferences the customer mentions."""
    prefs = set()
    for msg in user_messages:
        for match in PREFERENCE_PATTERN.finditer(msg):
            val = match.group(1).strip()
            if val and len(val) > 2:
                # Filter out common false positives
                if val.lower() not in ("to", "a", "an", "the", "some", "that", "this"):
                    prefs.add(val)
    return list(prefs)


def _extract_dietary(user_messages: list[str]) -> list[str]:
    """Extract dietary restrictions or allergies."""
    restrictions = set()
    for msg in user_messages:
        for match in DIETARY_PATTERN.finditer(msg):
            restrictions.add(match.group(0).strip().lower())
    return list(restrictions)


def _extract_dislikes(user_messages: list[str]) -> list[str]:
    """Extract foods/ingredients the customer dislikes."""
    dislikes = set()
    for msg in user_messages:
        for match in DISLIKE_PATTERN.finditer(msg):
            val = match.group(1).strip()
            if val:
                dislikes.add(val.lower())
    return list(dislikes)


def _extract_spice_tolerance(user_messages: list[str]) -> str | None:
    """Extract spice tolerance level."""
    for msg in user_messages:
        match = SPICE_PATTERN.search(msg)
        if match:
            return match.group(0).lower()
    return None


def _extract_cuisine(user_messages: list[str]) -> str | None:
    """Extract preferred cuisine type."""
    for msg in user_messages:
        match = CUISINE_PATTERN.search(msg)
        if match:
            return match.group(0).lower()
    return None


def _extract_budget(user_messages: list[str]) -> str | None:
    """Extract budget range mentions."""
    for msg in user_messages:
        match = BUDGET_PATTERN.search(msg)
        if match:
            return match.group(0).strip()
    return None


def _extract_delivery_method(user_messages: list[str]) -> str | None:
    """Extract delivery method preference."""
    for msg in user_messages:
        match = DELIVERY_PATTERN.search(msg)
        if match:
            matched = match.group(0).lower()
            if matched in ("delivery",):
                return "delivery"
            elif matched in ("takeaway", "pickup"):
                return "pickup"
            elif matched in ("dine-in", "eat-in"):
                return "dine_in"
    return None


# ── Main summarizer ───────────────────────────────────────────────────


def summarize_conversation(
    user_messages: list[str],
    assistant_messages: list[str],
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Analyze a conversation's messages and extract durable facts.

    Args:
        user_messages: List of user message strings.
        assistant_messages: List of assistant response strings.
        tool_calls: Optional list of tool call dicts with name, args, success.

    Returns:
        A dict with:
        - ``name``: Customer name or None.
        - ``email``: Customer email or None.
        - ``phone``: Customer phone or None.
        - ``preferences``: List of food/drink preferences.
        - ``dietary_restrictions``: List of dietary restrictions.
        - ``dislikes``: List of disliked foods/ingredients.
        - ``spice_tolerance``: Spice tolerance or None.
        - ``cuisine``: Preferred cuisine or None.
        - ``budget``: Budget range or None.
        - ``delivery_method``: Delivery preference or None.
        - ``summary_text``: Short plain-text summary of the conversation.
    """
    result: dict[str, Any] = {
        "name": _extract_name(user_messages),
        "email": _extract_email(user_messages),
        "phone": _extract_phone(user_messages),
        "preferences": _extract_preferences(user_messages),
        "dietary_restrictions": _extract_dietary(user_messages),
        "dislikes": _extract_dislikes(user_messages),
        "spice_tolerance": _extract_spice_tolerance(user_messages),
        "cuisine": _extract_cuisine(user_messages),
        "budget": _extract_budget(user_messages),
        "delivery_method": _extract_delivery_method(user_messages),
    }

    # Build a short summary
    summary_parts: list[str] = []
    if result["name"]:
        summary_parts.append(f"Customer: {result['name']}")
    if result["preferences"]:
        summary_parts.append(f"Likes: {', '.join(result['preferences'][:3])}")
    if result["dietary_restrictions"]:
        summary_parts.append(f"Dietary: {', '.join(result['dietary_restrictions'][:2])}")
    if result["cuisine"]:
        summary_parts.append(f"Cuisine: {result['cuisine']}")
    if tool_calls:
        order_placed = any(
            t.get("name") in ("submit_order", "initiate_payment") and t.get("success")
            for t in tool_calls
        )
        reservation_made = any(
            t.get("name") in ("confirm_reservation", "hold_reservation") and t.get("success")
            for t in tool_calls
        )
        if order_placed:
            summary_parts.append("Order placed")
        if reservation_made:
            summary_parts.append("Reservation made")

    result["summary_text"] = " | ".join(summary_parts) if summary_parts else "Casual inquiry"
    return result


async def persist_summary(
    memory_manager: "MemoryManager",
    *,
    customer_id: str,
    conversation_id: str | None = None,
    user_messages: list[str],
    assistant_messages: list[str],
    tool_calls: list[dict[str, Any]] | None = None,
    session=None,
) -> str:
    """Run the summarizer and persist extracted facts into long-term memory.

    This is the main entry point called from the agent controller.

    Args:
        memory_manager: The MemoryManager instance to persist facts.
        customer_id: The customer's ID string.
        conversation_id: Optional conversation/session ID.
        user_messages: List of user message strings from the conversation.
        assistant_messages: List of assistant response strings.
        tool_calls: Optional list of tool call dicts with name, args, success.
        session: Optional AgentSession instance; summary will be stored in metadata.

    Returns:
        The summary text string.
    """
    summary = summarize_conversation(user_messages, assistant_messages, tool_calls)

    # Persist each fact
    if summary["name"]:
        await sync_to_async(memory_manager.learn_fact)(
            customer_id=customer_id,
            category="preference",
            fact_key="name",
            fact_value=summary["name"],
            conversation_id=conversation_id,
        )

    if summary["email"]:
        await sync_to_async(memory_manager.learn_fact)(
            customer_id=customer_id,
            category="preference",
            fact_key="email",
            fact_value=summary["email"],
            conversation_id=conversation_id,
        )

    if summary["phone"]:
        await sync_to_async(memory_manager.learn_fact)(
            customer_id=customer_id,
            category="preference",
            fact_key="phone",
            fact_value=summary["phone"],
            conversation_id=conversation_id,
        )

    if summary["cuisine"]:
        await sync_to_async(memory_manager.learn_fact)(
            customer_id=customer_id,
            category="cuisine",
            fact_key="preferred_cuisine",
            fact_value=summary["cuisine"],
            conversation_id=conversation_id,
        )

    if summary["spice_tolerance"]:
        await sync_to_async(memory_manager.learn_fact)(
            customer_id=customer_id,
            category="spice",
            fact_key="spice_tolerance",
            fact_value=summary["spice_tolerance"],
            conversation_id=conversation_id,
        )

    if summary["budget"]:
        await sync_to_async(memory_manager.learn_fact)(
            customer_id=customer_id,
            category="budget",
            fact_key="budget_range",
            fact_value=summary["budget"],
            conversation_id=conversation_id,
        )

    if summary["delivery_method"]:
        await sync_to_async(memory_manager.learn_fact)(
            customer_id=customer_id,
            category="preference",
            fact_key="preferred_delivery",
            fact_value=summary["delivery_method"],
            conversation_id=conversation_id,
        )

    for pref in summary["preferences"]:
        await sync_to_async(memory_manager.learn_fact)(
            customer_id=customer_id,
            category="preference",
            fact_key=f"likes_{pref.lower().replace(' ', '_')}",
            fact_value=pref,
            conversation_id=conversation_id,
        )

    for dietary in summary["dietary_restrictions"]:
        await sync_to_async(memory_manager.learn_fact)(
            customer_id=customer_id,
            category="dietary",
            fact_key=f"dietary_{dietary[:40].replace(' ', '_')}",
            fact_value=dietary,
            conversation_id=conversation_id,
        )

    for dislike in summary["dislikes"]:
        await sync_to_async(memory_manager.learn_fact)(
            customer_id=customer_id,
            category="dislike",
            fact_key=f"dislikes_{dislike.replace(' ', '_')}",
            fact_value=dislike,
            conversation_id=conversation_id,
        )

    # Update customer profile after new facts
    await sync_to_async(memory_manager.update_profile)(customer_id=customer_id)

    # Store summary in session metadata if available
    if session is not None and hasattr(session, "metadata"):
        session.metadata["summary"] = summary["summary_text"]
        await sync_to_async(session.save)(update_fields=["metadata"])

    logger.info(
        "Conversation summary persisted for customer=%s: %s",
        customer_id,
        summary["summary_text"],
    )

    return summary["summary_text"]
