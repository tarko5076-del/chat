"""ManagePreferencesTool — explicit customer-facing memory management.

Allows customers to:
- Set a favorite item (set_favorite)
- Set a general preference (set_preference)
- View their full profile (get_my_profile)
- View their usual order (get_usual_order)

This tool is registered alongside all other agent tools and callable
both by the LLM and the LocalPlanner.
"""

from __future__ import annotations

import logging
from typing import Any

from agent.memory_manager import MemoryManager
from agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ManagePreferencesTool(BaseTool):
    """Manage customer preferences, favorites, and profile.

    Actions:
    - set_favorite: Save a favorite item (e.g., "Ethiopian coffee")
    - set_preference: Save a general preference (key-value pair)
    - get_my_profile: Return the customer's full profile
    - get_usual_order: Return the customer's most-ordered item
    """

    name: str = "manage_preferences"
    description: str = (
        "Manage customer preferences, favorites, and profile. "
        "Use this when the customer says something like 'my favorite is...', "
        "'I like...', 'set my preference...', 'what do you know about me?', "
        "'show my profile', or 'what's my usual order?'."
    )
    parameters: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": "The action to perform",
                "enum": ["set_favorite", "set_preference", "get_my_profile", "get_usual_order"],
            },
            "item_name": {
                "type": "string",
                "description": "Item name for set_favorite action (e.g., 'Ethiopian coffee')",
            },
            "key": {
                "type": "string",
                "description": "Preference key for set_preference (e.g., 'spice_tolerance', 'preferred_cuisine')",
            },
            "value": {
                "type": "string",
                "description": "Preference value for set_preference (e.g., 'high', 'italian')",
            },
            "customer_id": {
                "type": "string",
                "description": "Customer ID for scoping the operation",
            },
        },
        "required": ["action"],
    }

    def __init__(self) -> None:
        self.memory_manager = MemoryManager()

    def execute(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "")
        customer_id = kwargs.get("customer_id", "")

        if not customer_id:
            return ToolResult(
                success=False,
                message="I need to know who you are to manage your preferences. Please log in first.",
                missing_fields=["customer_id"],
            )

        if action == "set_favorite":
            return self._set_favorite(kwargs)
        elif action == "set_preference":
            return self._set_preference(kwargs)
        elif action == "get_my_profile":
            return self._get_profile(kwargs)
        elif action == "get_usual_order":
            return self._get_usual_order(kwargs)
        else:
            return ToolResult(
                success=False,
                message=f"Unknown action '{action}'. Available actions: set_favorite, set_preference, get_my_profile, get_usual_order.",
            )

    def _set_favorite(self, kwargs: dict[str, Any]) -> ToolResult:
        customer_id = kwargs.get("customer_id", "")
        item_name = kwargs.get("item_name", "")

        if not item_name:
            return ToolResult(
                success=False,
                message="What item would you like to set as your favorite?",
                missing_fields=["item_name"],
            )

        # Save as semantic fact
        self.memory_manager.learn_fact(
            customer_id=customer_id,
            category="favorite",
            fact_key=f"favorite_{item_name.lower().replace(' ', '_')}",
            fact_value=item_name,
        )

        # Also save as "last_favorite" for easy lookup
        self.memory_manager.learn_fact(
            customer_id=customer_id,
            category="favorite",
            fact_key="last_favorite",
            fact_value=item_name,
        )

        # Update profile
        self.memory_manager.update_profile(customer_id=customer_id)

        logger.info("Favorite set: customer=%s item=%s", customer_id, item_name)

        return ToolResult(
            success=True,
            message=f"Got it! I've saved '{item_name}' as your favorite.",
            data={"item_name": item_name},
            memory_updates={"favorite_item": item_name},
        )

    def _set_preference(self, kwargs: dict[str, Any]) -> ToolResult:
        customer_id = kwargs.get("customer_id", "")
        key = kwargs.get("key", "")
        value = kwargs.get("value", "")

        if not key or not value:
            return ToolResult(
                success=False,
                message="Please provide both a preference key and value. For example: key='spice_tolerance', value='high'.",
                missing_fields=[k for k in ("key", "value") if not kwargs.get(k)],
            )

        # Map common keys to SemanticMemory categories
        category_map: dict[str, str] = {
            "spice_tolerance": "spice",
            "preferred_cuisine": "cuisine",
            "dietary_restriction": "dietary",
            "budget_range": "budget",
            "preferred_payment": "preference",
            "preferred_delivery": "preference",
        }
        category = category_map.get(key, "preference")

        self.memory_manager.learn_fact(
            customer_id=customer_id,
            category=category,
            fact_key=key,
            fact_value=value,
        )

        # Update profile
        self.memory_manager.update_profile(customer_id=customer_id)

        logger.info("Preference set: customer=%s key=%s value=%s", customer_id, key, value)

        return ToolResult(
            success=True,
            message=f"I've saved that preference: {key} = {value}.",
            data={"key": key, "value": value},
            memory_updates={key: value},
        )

    def _get_profile(self, kwargs: dict[str, Any]) -> ToolResult:
        customer_id = kwargs.get("customer_id", "")
        profile = self.memory_manager.get_profile(customer_id=customer_id)

        if not profile:
            return ToolResult(
                success=True,
                message="I don't have a profile for you yet. As you chat with me, I'll learn your preferences automatically!",
                data={"profile": None},
            )

        profile_data = {
            "display_name": profile.display_name or "",
            "preferred_cuisine": profile.preferred_cuisine or "",
            "dietary_restrictions": profile.dietary_restrictions or "",
            "spice_tolerance": profile.spice_tolerance or "",
            "budget_range": profile.budget_range or "",
            "favorite_items": [i.strip() for i in (profile.favorite_items or "").split(",") if i.strip()],
            "total_orders": profile.total_orders,
            "total_reservations": profile.total_reservations,
        }

        # Build natural language description
        parts = []
        if profile.display_name:
            parts.append(f"your name is {profile.display_name}")
        if profile_data["favorite_items"]:
            items = ", ".join(profile_data["favorite_items"])
            parts.append(f"your favorites include {items}")
        if profile.dietary_restrictions:
            parts.append(f"you have these dietary preferences: {profile.dietary_restrictions}")
        if profile.preferred_cuisine:
            parts.append(f"you prefer {profile.preferred_cuisine} cuisine")
        if profile.spice_tolerance:
            parts.append(f"you like {profile.spice_tolerance} spice levels")
        if profile.total_orders:
            parts.append(f"you've placed {profile.total_orders} orders with us")

        description = "I know that " + ", and ".join(parts) + "." if parts else "No preferences saved yet."

        return ToolResult(
            success=True,
            message=description,
            data={"profile": profile_data},
        )

    def _get_usual_order(self, kwargs: dict[str, Any]) -> ToolResult:
        customer_id = kwargs.get("customer_id", "")
        from agent.memory_engine import MemoryEngine
        engine = MemoryEngine(self.memory_manager)
        usual = engine.get_usual_order(customer_id)

        if not usual:
            return ToolResult(
                success=True,
                message="I don't have a usual order for you yet. Once you place a few orders, I'll remember what you typically get!",
                data={"usual_order": None},
            )

        return ToolResult(
            success=True,
            message=f"Your usual order is {usual['item_name']} — you've ordered it {usual['order_count']} time(s).",
            data={"usual_order": usual},
        )
