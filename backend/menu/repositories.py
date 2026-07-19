from typing import Any

from django.db.models import Q, QuerySet

from menu.models import MenuItem


class MenuRepository:
    """Database access layer for MenuItem model."""

    # ── Queries ───────────────────────────────────────────────────────────

    def get_by_id(self, item_id: int) -> MenuItem | None:
        return MenuItem.objects.filter(id=item_id).first()

    def get_available(self) -> QuerySet[MenuItem]:
        return MenuItem.objects.filter(available=True)

    def list_all(self) -> list[MenuItem]:
        return list(MenuItem.objects.all().order_by("category", "name"))

    def get_categories(self) -> list[str]:
        """Return distinct category names from available items, sorted."""
        return list(
            MenuItem.objects.filter(available=True)
            .values_list("category", flat=True)
            .distinct()
            .order_by("category")
        )

    def get_items_by_ids(self, ids: list[int]) -> list[MenuItem]:
        """Bulk lookup by primary key. Only returns available items."""
        return list(MenuItem.objects.filter(id__in=ids, available=True))

    def search_by_allergens(self, exclude_allergens: str) -> list[MenuItem]:
        """Find available menu items that do NOT contain the given allergen(s).

        Performs a case-insensitive exclusion check against the allergens field.
        Items with an empty allergens field pass the filter.
        """
        qs = MenuItem.objects.filter(available=True)
        for term in exclude_allergens.lower().split(","):
            term = term.strip()
            if term:
                qs = qs.exclude(allergens__icontains=term)
        return list(qs.order_by("category", "name"))

    def search_by_dietary_need(self, dietary: str) -> list[MenuItem]:
        """Find menu items matching a dietary need keyword.

        Supports: 'vegetarian', 'vegan', 'gluten-free', 'dairy-free'
        """
        qs = MenuItem.objects.filter(available=True)
        dietary_lower = dietary.lower()

        if "vegetarian" in dietary_lower:
            qs = qs.filter(vegetarian=True)
        if "vegan" in dietary_lower:
            qs = qs.filter(vegan=True)
        if "gluten" in dietary_lower:
            qs = qs.exclude(allergens__icontains="gluten")
        if "dairy" in dietary_lower:
            qs = qs.exclude(allergens__icontains="dairy")

        return list(qs.order_by("category", "name"))

    def search(self, **filters: Any) -> list[MenuItem]:
        """Search menu items by category, dietary flags, price, and text search."""
        qs = MenuItem.objects.filter(available=True)

        if category := filters.get("category"):
            qs = qs.filter(category=category)
        if filters.get("vegetarian"):
            qs = qs.filter(vegetarian=True)
        if filters.get("vegan"):
            qs = qs.filter(vegan=True)
        if filters.get("spicy"):
            qs = qs.filter(spicy=True)
        if max_price := filters.get("max_price"):
            qs = qs.filter(price__lte=max_price)
        if search := filters.get("search"):
            qs = qs.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )

        return list(qs.order_by("category", "price")[:20])

    def find_alternatives(
        self,
        *,
        exclude_id: int | None = None,
        name_words: set[str] = set(),
        description_words: set[str] = set(),
        category: str | None = None,
        vegetarian: bool | None = None,
        spicy: bool | None = None,
        max_results: int = 3,
    ) -> list[MenuItem]:
        """Find similar menu items by word matching and category affinity."""
        available = list(MenuItem.objects.filter(available=True))
        scored: list[tuple[int, float, MenuItem]] = []

        for candidate in available:
            if exclude_id and candidate.id == exclude_id:
                continue

            score = 0
            candidate_words = set(candidate.name.lower().split())
            if description_words:
                candidate_words |= set(candidate.description.lower().split())

            score += len(name_words & candidate_words)
            score += len(description_words & candidate_words)

            if category and candidate.category == category:
                score += 5
            if vegetarian is not None and candidate.vegetarian == vegetarian:
                score += 1
            if spicy is not None and candidate.spicy == spicy:
                score += 1

            # Fallback: if nothing matched, give a minimal score so we still return something
            if score == 0 and not name_words and not description_words:
                score = 1

            if score > 0:
                scored.append((score, -float(candidate.price), candidate))

        scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
        return [item for _, _, item in scored[:max_results]]
