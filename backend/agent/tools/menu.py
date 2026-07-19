import logging

from menu.services import MenuService, MenuNotFoundError
from agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class MenuTool(BaseTool):
    name = "list_menu_items"
    description = (
        "List, search, or filter available menu items by category, dietary "
        "preferences (vegetarian, vegan, spicy), price range, allergens, "
        "dietary needs, or free-text search."
    )
    parameters = {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "description": "Menu category to filter by "
                               "(e.g. 'Wot (Stews)', 'Tibs (Sautéed)', 'Drinks')",
            },
            "vegetarian": {"type": "boolean"},
            "vegan": {"type": "boolean"},
            "spicy": {"type": "boolean"},
            "max_price": {"type": "number"},
            "search": {
                "type": "string",
                "description": "Free-text search in item name and description",
            },
            "query": {
                "type": "string",
                "description": "Natural language query — auto-detects dietary "
                               "preferences, price hints, and category mentions",
            },
            "allergens": {
                "type": "string",
                "description": "Comma-separated allergens to EXCLUDE "
                               "(e.g. 'gluten, dairy')",
            },
            "dietary": {
                "type": "string",
                "description": "Dietary need filter "
                               "(e.g. 'vegetarian', 'vegan', 'gluten-free')",
            },
        },
    }

    def __init__(self):
        super().__init__()
        self.service = MenuService()

    def execute(self, **kwargs):
        items = self._search(kwargs)
        if not items:
            logger.info("action=search filters=%s result=empty", kwargs)
            return ToolResult(
                success=True,
                message="No menu items found matching your criteria.",
                data={"items": [], "filters": kwargs},
                next_action="ask_user",
            )

        logger.info("action=search filters=%s result=%d_items", kwargs, len(items))
        return ToolResult(
            success=True,
            message=self._format_items(items),
            data={"items": [self._item_data(item) for item in items], "filters": kwargs},
        )

    def _search(self, kwargs):
        """Route to the appropriate search method based on params."""
        # Allergen exclusion takes priority if specified
        if allergens := kwargs.get("allergens"):
            return self.service.search_by_allergen(allergens)

        # Dietary need filter
        if dietary := kwargs.get("dietary"):
            return self.service.search_by_dietary(dietary)

        # Natural language query — pop 'query' to avoid double-passing
        if query := kwargs.get("query"):
            remaining = {k: v for k, v in kwargs.items() if k != "query"}
            return self.service.search_natural(query, **remaining)

        # Standard structured search
        return self.service.search(**kwargs)

    def _format_items(self, items):
        lines = ["Here are good menu options:"]
        for item in items:
            tags = self._tags(item)
            suffix = f" [{', '.join(tags)}]" if tags else ""
            lines.append(
                f"- {item.name}: ${item.price:.2f} ({item.category}) - "
                f"{item.description}{suffix}"
            )
        return "\n".join(lines)

    def _tags(self, item):
        tags = []
        if item.vegetarian:
            tags.append("vegetarian")
        if item.vegan:
            tags.append("vegan")
        if item.spicy:
            tags.append("spicy")
        return tags

    def _item_data(self, item):
        return {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "category": item.category,
            "price": float(item.price),
            "vegetarian": item.vegetarian,
            "vegan": item.vegan,
            "spicy": item.spicy,
            "allergens": item.allergens,
        }


class GetMenuItemDetailsTool(BaseTool):
    name = "get_menu_item_details"
    description = (
        "Get detailed information about a specific menu item, including "
        "allergens, dietary flags, and optionally similar items."
    )
    parameters = {
        "type": "object",
        "properties": {
            "item_id": {
                "type": "integer",
                "description": "The ID of the menu item",
            },
            "include_similar": {
                "type": "boolean",
                "description": "Whether to include similar menu items (default false)",
            },
        },
        "required": ["item_id"],
    }

    def __init__(self):
        super().__init__()
        self.service = MenuService()

    def execute(self, **kwargs):
        item_id = kwargs.get("item_id")
        if not item_id:
            return ToolResult(
                success=False,
                message="Please provide a menu item ID.",
                missing_fields=["item_id"],
                next_action="ask_user",
            )

        include_similar = kwargs.get("include_similar", False)
        details = self.service.get_item_with_details(
            item_id=item_id,
            include_similar=include_similar,
        )

        if not details:
            return ToolResult(
                success=False,
                message=f"I could not find a menu item with ID {item_id}.",
                data={"item_id": item_id},
                next_action="ask_user",
            )

        tags = []
        if details.get("vegetarian"):
            tags.append("vegetarian")
        if details.get("vegan"):
            tags.append("vegan")
        if details.get("spicy"):
            tags.append("spicy")

        tag_suffix = f" [{', '.join(tags)}]" if tags else ""
        similar_text = ""
        if include_similar and details.get("similar_items"):
            similar_list = details["similar_items"]
            similar_text = "\n\nSimilar items you might enjoy:\n" + "\n".join(
                f"- {s['name']}: ${float(s['price']):.2f}"
                for s in similar_list
            )

        message = (
            f"{details['name']} — ${float(details['price']):.2f}{tag_suffix}\n"
            f"Category: {details['category']}\n"
            f"Description: {details['description']}\n"
            f"Availability: {'Available' if details.get('available', True) else 'Sold out'}"
        )
        if details.get("allergens"):
            message += f"\nAllergens: {details['allergens']}"
        if tags:
            message += f"\nDietary: {', '.join(tags)}"
        message += similar_text

        return ToolResult(
            success=True,
            message=message,
            data=details,
        )
