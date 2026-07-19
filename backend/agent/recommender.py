"""Recommendation engine for personalized menu suggestions.

Combines customer memory (past orders, preferences) with menu data
to produce tailored recommendations with explanations.
"""

import logging
from typing import Any

from menu.models import MenuItem
from menu.services import MenuService

logger = logging.getLogger(__name__)


class RecommendationService:
    """Scoring-based recommendation engine for menu items."""

    def __init__(self, menu_service: MenuService | None = None) -> None:
        self.menu_service = menu_service or MenuService()

    def recommend(
        self,
        *,
        preferences: dict[str, Any] | None = None,
        customer_profile: dict[str, Any] | None = None,
        count: int = 3,
    ) -> list[dict[str, Any]]:
        """Generate personalized menu recommendations.

        Parameters:
            preferences: Dict of desired filters (vegetarian, vegan, spicy,
                         max_price, category, query, dietary)
            customer_profile: Dict with keys like dietary_restrictions,
                              spice_tolerance, favorite_items, budget_range
                              (from CustomerProfile or memory)
            count: Maximum number of recommendations to return

        Returns:
            List of dicts with keys: item, score, reasons
        """
        items = self.menu_service.list_all()
        available = [item for item in items if item.available]
        if not available:
            return []

        prefs = preferences or {}

        # Apply hard pre-filters based on explicit preferences
        # Boolean flags filter strictly; max_price, category, dietary also filter
        candidates = list(available)
        if prefs.get("vegetarian"):
            candidates = [i for i in candidates if i.vegetarian]
        if prefs.get("vegan"):
            candidates = [i for i in candidates if i.vegan]
        if prefs.get("spicy"):
            candidates = [i for i in candidates if i.spicy]
        if max_price := prefs.get("max_price"):
            candidates = [i for i in candidates if float(i.price) <= float(max_price)]
        if category := prefs.get("category"):
            candidates = [i for i in candidates if i.category.lower() == category.lower()]
        if dietary := prefs.get("dietary"):
            d = dietary.lower()
            if "vegan" in d:
                candidates = [i for i in candidates if i.vegan]
            if "vegetarian" in d:
                candidates = [i for i in candidates if i.vegetarian]
            if "gluten" in d:
                candidates = [i for i in candidates if "gluten" not in i.allergens.lower()]

        if not candidates:
            return []

        # Score each candidate item
        scored: list[tuple[float, MenuItem, list[str]]] = []
        for item in candidates:
            score, reasons = self._score_item(
                item,
                preferences=prefs,
                profile=customer_profile,
            )
            if score > 0:
                scored.append((score, item, reasons))

        # Sort by score descending
        scored.sort(key=lambda row: row[0], reverse=True)

        # Take top N
        top = scored[:count]

        return [
            {
                "item": self._item_summary(item),
                "score": round(score, 1),
                "reasons": reasons,
            }
            for score, item, reasons in top
        ]

    def _score_item(
        self,
        item: MenuItem,
        *,
        preferences: dict[str, Any],
        profile: dict[str, Any] | None,
    ) -> tuple[float, list[str]]:
        """Score a single menu item against preferences and profile.

        Returns (score, list_of_reasons).
        """
        score = 0.0
        reasons: list[str] = []

        # ── Preference matching ───────────────────────────────────────────
        if preferences.get("vegetarian") and item.vegetarian:
            score += 10
            reasons.append("vegetarian-friendly")

        if preferences.get("vegan") and item.vegan:
            score += 10
            reasons.append("vegan-friendly")

        if preferences.get("spicy") and item.spicy:
            score += 8
            reasons.append("has the spicy kick you asked for")
        elif preferences.get("spicy") is False and not item.spicy:
            score += 5
            reasons.append("mild and not spicy")

        if max_price := preferences.get("max_price"):
            if float(item.price) <= float(max_price):
                score += 5
                reasons.append(f"under ${float(max_price):.2f}")
            else:
                # Item exceeds budget — still possible but penalized
                score -= 2

        if category := preferences.get("category"):
            if item.category.lower() == category.lower():
                score += 6
                reasons.append(f"from the {item.category} category")

        if query := preferences.get("query"):
            q = query.lower()
            if q in item.name.lower():
                score += 12
            elif q in item.description.lower():
                score += 8

        if dietary := preferences.get("dietary"):
            d = dietary.lower()
            if "vegetarian" in d and item.vegetarian:
                score += 8
                reasons.append("suitable for vegetarians")
            elif "vegan" in d and item.vegan:
                score += 8
                reasons.append("suitable for vegans")
            if "gluten" in d and "gluten" not in item.allergens.lower():
                score += 6
                reasons.append("gluten-free option")

        # ── Customer profile matching ──────────────────────────────────────
        if profile:
            if restrictions := profile.get("dietary_restrictions", ""):
                r_lower = restrictions.lower()
                if "vegetarian" in r_lower and item.vegetarian:
                    score += 8
                    reasons.append("matches your vegetarian preference")
                elif "vegan" in r_lower and item.vegan:
                    score += 8
                    reasons.append("matches your vegan preference")
                # Check allergen avoidance
                for allergen in ["nuts", "dairy", "gluten", "eggs", "shellfish"]:
                    if allergen in r_lower and allergen not in item.allergens.lower():
                        score += 4
                        if not any(allergen in r for r in reasons):
                            reasons.append(f"free from {allergen}")

            if spice := profile.get("spice_tolerance", ""):
                s_lower = spice.lower()
                if "high" in s_lower and item.spicy:
                    score += 5
                    reasons.append("nice and spicy, just how you like it")
                elif ("low" in s_lower or "none" in s_lower) and not item.spicy:
                    score += 5
                    reasons.append("mild, as you prefer")

            if fav := profile.get("favorite_items", ""):
                if item.name.lower() in fav.lower():
                    score += 20
                    reasons.append("one of your favorites!")

            if budget := profile.get("budget_range", ""):
                try:
                    budget_val = float(budget.replace("$", "").strip())
                    if float(item.price) <= budget_val:
                        score += 3
                except (ValueError, AttributeError):
                    pass

        # ── Fallback for when no preferences at all ───────────────────────
        if not reasons:
            # Only give a fallback score if NO preferences were specified
            # (user just asked for recommendations without any criteria).
            # If preferences were specified and nothing matched, score stays 0.
            has_preferences = bool(
                preferences.get("vegetarian")
                or preferences.get("vegan")
                or preferences.get("spicy")
                or preferences.get("max_price")
                or preferences.get("category")
                or preferences.get("query")
                or preferences.get("dietary")
            )
            if not has_preferences and not profile:
                score = max(score, 1.0)
                reasons.append("popular choice")

        return score, reasons

    def _item_summary(self, item: MenuItem) -> dict[str, Any]:
        """Return a summary dict for a menu item."""
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
