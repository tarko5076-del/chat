import logging

from agent.recommender import RecommendationService
from agent.tools.base import BaseTool, ToolResult
from agent.memory_manager import MemoryManager

logger = logging.getLogger(__name__)


class RecommendMenuTool(BaseTool):
    name = "recommend_menu_items"
    description = (
        "Recommend menu items based on customer preferences, dietary needs, "
        "and past order history. Provide personalized suggestions with reasons."
    )
    parameters = {
        "type": "object",
        "properties": {
            "preferences": {
                "type": "object",
                "description": "Optional preferences: vegetarian, vegan, spicy (bool), "
                               "max_price (number), category (string), "
                               "query (string), dietary (string e.g. 'vegetarian')",
                "properties": {
                    "vegetarian": {"type": "boolean"},
                    "vegan": {"type": "boolean"},
                    "spicy": {"type": "boolean"},
                    "max_price": {"type": "number"},
                    "category": {"type": "string"},
                    "query": {"type": "string", "description": "Natural language search"},
                    "dietary": {"type": "string", "description": "Dietary need like 'vegetarian'"},
                },
            },
            "customer_id": {
                "type": "string",
                "description": "Customer ID for personalized recommendations using memory",
            },
            "count": {
                "type": "integer",
                "description": "Number of recommendations to return (default 3)",
            },
        },
    }

    def __init__(self):
        super().__init__()
        self.recommender = RecommendationService()
        self.memory_manager = MemoryManager()

    def execute(self, **kwargs):
        preferences = kwargs.get("preferences") or {}
        customer_id = kwargs.get("customer_id")
        count = min(int(kwargs.get("count", 3)), 10)

        # Load customer profile from long-term memory if available
        customer_profile = None
        if customer_id:
            try:
                memory_facts = self.memory_manager.get_semantic_facts(
                    customer_id=customer_id,
                )
                customer_profile = self._build_profile(memory_facts)
            except Exception:
                logger.debug("Failed to load customer profile for recommendations", exc_info=True)

        recommendations = self.recommender.recommend(
            preferences=preferences,
            customer_profile=customer_profile,
            count=count,
        )

        if not recommendations:
            return ToolResult(
                success=True,
                message="I could not find any menu items matching your preferences right now.",
                data={"recommendations": [], "preferences": preferences},
                next_action="ask_user",
            )

        return ToolResult(
            success=True,
            message=self._format_recommendations(recommendations),
            data={
                "recommendations": recommendations,
                "preferences": preferences,
                "count": len(recommendations),
            },
        )

    def _build_profile(self, memory_facts: list | None) -> dict | None:
        """Build a customer profile dict from semantic memory facts."""
        if not memory_facts:
            return None

        profile = {}
        for fact in memory_facts:
            key = fact.get("fact_key") or fact.get("key", "")
            value = fact.get("fact_value") or fact.get("value", "")

            if "diet" in key.lower() or "restriction" in key.lower():
                profile["dietary_restrictions"] = value
            elif "spice" in key.lower():
                profile["spice_tolerance"] = value
            elif "favorite" in key.lower() or "favourite" in key.lower():
                profile["favorite_items"] = value
            elif "budget" in key.lower():
                profile["budget_range"] = value

        return profile or None

    def _format_recommendations(self, recommendations: list[dict]) -> str:
        """Format recommendations into a natural language message."""
        lines = ["Here are my recommendations for you:\n"]
        for i, rec in enumerate(recommendations, 1):
            item = rec["item"]
            reasons = rec.get("reasons", [])
            reason_text = f" — {', '.join(reasons)}" if reasons else ""
            lines.append(
                f"{i}. **{item['name']}** — ${float(item['price']):.2f}"
                f"{reason_text}"
            )
            lines.append(f"   {item['description']}\n")

        return "\n".join(lines).strip()
