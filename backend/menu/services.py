import logging
import re
from typing import Any

from menu.models import MenuItem
from menu.repositories import MenuRepository

logger = logging.getLogger(__name__)


class MenuNotFoundError(Exception):
    pass


class MenuService:
    """Business logic for menu queries and recommendations."""

    def __init__(self) -> None:
        self.repo = MenuRepository()

    def list_all(self) -> list[MenuItem]:
        return self.repo.list_all()

    def get_item(self, item_id: int) -> MenuItem | None:
        """Get a menu item by ID, or None if not found."""
        item = self.repo.get_by_id(item_id)
        if not item:
            return None
        return item

    def get_categories(self) -> list[str]:
        """Return all distinct menu categories."""
        return self.repo.get_categories()

    def get_item_with_details(
        self,
        item_id: int,
        include_similar: bool = False,
    ) -> dict | None:
        """Get a menu item with full details and optional similar items."""
        item = self.repo.get_by_id(item_id)
        if not item:
            return None

        result = item.to_dict()
        result["allergens"] = item.allergens
        result["available"] = item.available

        if include_similar:
            similar = self.find_alternatives(item=item, max_results=3)
            result["similar_items"] = [s.to_dict() for s in similar]

        return result

    def search(self, **filters: Any) -> list[MenuItem]:
        """Search menu items by various criteria."""
        return self.repo.search(**filters)

    def search_natural(self, query: str, **filters: Any) -> list[MenuItem]:
        """Search menu items using a natural language query string.

        Parses common dietary/preference keywords from the query and
        applies them as structured filters alongside keyword search.
        """
        q = query.lower()

        # Auto-detect dietary preferences from natural language
        if "vegetarian" in q or "veg" in q:
            filters.setdefault("vegetarian", True)
        if "vegan" in q:
            filters.setdefault("vegan", True)
        if "spicy" in q or "spice" in q or "hot" in q:
            filters.setdefault("spicy", True)

        # Auto-detect price from phrases like "under $15" or "under 15 dollars"
        price_match = re.search(r"under\s*\$?(\d+(?:\.\d{1,2})?)", q)
        if price_match:
            filters.setdefault("max_price", float(price_match.group(1)))

        # Auto-detect category mentions
        categories = self.repo.get_categories()
        for cat in categories:
            if cat.lower() in q or cat.split("(")[0].strip().lower() in q:
                filters["category"] = cat
                break

        # Use the query as a text search if no other structural filter applied
        if not any(k in filters for k in ["vegetarian", "vegan", "spicy", "max_price", "category"]):
            filters["search"] = query

        return self.repo.search(**filters)

    def search_by_allergen(self, allergen: str) -> list[MenuItem]:
        """Find menu items that do NOT contain the given allergen."""
        return self.repo.search_by_allergens(allergen)

    def search_by_dietary(self, dietary: str) -> list[MenuItem]:
        """Find menu items matching a dietary need."""
        return self.repo.search_by_dietary_need(dietary)

    def find_alternatives(
        self,
        *,
        item: MenuItem | None = None,
        requested_name: str | None = None,
        max_results: int = 3,
    ) -> list[MenuItem]:
        """Find alternatives similar to a given item or name."""
        name_words: set[str] = set()
        desc_words: set[str] = set()
        category: str | None = None
        vegetarian: bool | None = None
        spicy: bool | None = None
        exclude_id: int | None = None

        if item:
            name_words = set(item.name.lower().split())
            desc_words = set(item.description.lower().split())
            category = item.category
            vegetarian = item.vegetarian
            spicy = item.spicy
            exclude_id = item.id

        if requested_name:
            name_words |= set(requested_name.lower().split())

        return self.repo.find_alternatives(
            exclude_id=exclude_id,
            name_words=name_words,
            description_words=desc_words,
            category=category,
            vegetarian=vegetarian,
            spicy=spicy,
            max_results=max_results,
        )
