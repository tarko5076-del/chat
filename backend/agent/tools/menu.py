from menu.models import MenuItem
from agent.tools.base import BaseTool, ToolResult


class MenuTool(BaseTool):
    name = "list_menu_items"
    description = "List, search, filter, or recommend available menu items."
    parameters = {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": ["appetizer", "main", "dessert", "drink"]},
            "vegetarian": {"type": "boolean"},
            "vegan": {"type": "boolean"},
            "spicy": {"type": "boolean"},
            "max_price": {"type": "number"},
            "search": {"type": "string"},
        },
    }

    async def execute(self, **kwargs):
        from django.db.models import Q

        query = MenuItem.objects.filter(available=True)
        if category := kwargs.get("category"):
            query = query.filter(category=category)
        if kwargs.get("vegetarian"):
            query = query.filter(vegetarian=True)
        if kwargs.get("vegan"):
            query = query.filter(vegan=True)
        if kwargs.get("spicy"):
            query = query.filter(spicy=True)
        if max_price := kwargs.get("max_price"):
            query = query.filter(price__lte=max_price)
        if search := kwargs.get("search"):
            query = query.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )

        items = list(query.order_by("category", "price")[:8])
        if not items:
            return ToolResult(
                success=True,
                message="No menu items found matching your criteria.",
                data={"items": [], "filters": kwargs},
                next_action="ask_user",
            )
        return ToolResult(
            success=True,
            message=self._format_items(items),
            data={"items": [self._item_data(item) for item in items], "filters": kwargs},
        )

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
        }
