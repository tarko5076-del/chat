from typing import Any

from app.database import SessionLocal
from app.models.menu import MenuItem
from app.tools.base import BaseTool, ToolResult


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

    async def execute(self, **kwargs: Any) -> ToolResult:
        db = SessionLocal()
        try:
            query = db.query(MenuItem).filter(MenuItem.available.is_(True))
            if category := kwargs.get("category"):
                query = query.filter(MenuItem.category == category)
            if kwargs.get("vegetarian"):
                query = query.filter(MenuItem.vegetarian.is_(True))
            if kwargs.get("vegan"):
                query = query.filter(MenuItem.vegan.is_(True))
            if kwargs.get("spicy"):
                query = query.filter(MenuItem.spicy.is_(True))
            if max_price := kwargs.get("max_price"):
                query = query.filter(MenuItem.price <= max_price)
            if search := kwargs.get("search"):
                like = f"%{search.lower()}%"
                query = query.filter(MenuItem.name.ilike(like) | MenuItem.description.ilike(like))

            items = query.order_by(MenuItem.category, MenuItem.price).limit(8).all()
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
        finally:
            db.close()

    def _format_items(self, items: list[MenuItem]) -> str:
        lines = ["Here are good menu options:"]
        for item in items:
            tags = self._tags(item)
            suffix = f" [{', '.join(tags)}]" if tags else ""
            lines.append(
                f"- {item.name}: ${item.price:.2f} ({item.category}) - "
                f"{item.description}{suffix}"
            )
        return "\n".join(lines)

    def _tags(self, item: MenuItem) -> list[str]:
        tags = []
        if item.vegetarian:
            tags.append("vegetarian")
        if item.vegan:
            tags.append("vegan")
        if item.spicy:
            tags.append("spicy")
        return tags

    def _item_data(self, item: MenuItem) -> dict[str, Any]:
        return {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "category": item.category,
            "price": item.price,
            "vegetarian": item.vegetarian,
            "vegan": item.vegan,
            "spicy": item.spicy,
        }
