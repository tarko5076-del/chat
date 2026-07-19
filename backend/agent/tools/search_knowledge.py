from agent.rag import search_knowledge, format_knowledge_context
from agent.tools.base import BaseTool, ToolResult


class SearchKnowledgeTool(BaseTool):
    name = "search_knowledge"
    description = (
        "Search the restaurant's knowledge base for menu items, policies, FAQs, "
        "and promotions using advanced hybrid search (combines semantic understanding "
        "with keyword matching). Use this when the user asks about dishes, ingredients, "
        "allergens, restaurant rules, prices, or current deals."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language search query (e.g., 'gluten-free options under $15', 'cancellation policy', 'happy hour deals')",
            },
            "search_mode": {
                "type": "string",
                "enum": ["hybrid", "vector", "keyword"],
                "description": "Search mode: 'hybrid' (default, combines semantic + keyword), 'vector' (semantic only), 'keyword' (text match only)",
            },
            "content_type": {
                "type": "string",
                "enum": ["menu_item", "policy", "faq", "promotion"],
                "description": "Filter by content type (optional)",
            },
            "categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Filter by metadata categories (e.g., ['Mains', 'Drinks']). Only applies to menu_item results.",
            },
            "max_price": {
                "type": "number",
                "description": "Maximum price filter. Only applies to menu_item results with price metadata.",
            },
            "min_price": {
                "type": "number",
                "description": "Minimum price filter. Only applies to menu_item results.",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return (default 5, max 20)",
            },
        },
        "required": ["query"],
    }

    def execute(self, **kwargs):
        query = kwargs.get("query", "").strip()
        if not query:
            return ToolResult(
                success=False,
                message="Please provide a search query.",
                missing_fields=["query"],
                next_action="ask_user",
            )

        search_mode = kwargs.get("search_mode", "hybrid")
        content_type = kwargs.get("content_type")
        categories = kwargs.get("categories")
        max_price = kwargs.get("max_price")
        min_price = kwargs.get("min_price")
        top_k = kwargs.get("top_k", 5)

        results = search_knowledge(
            query,
            search_mode=search_mode,
            content_type=content_type,
            categories=categories,
            max_price=max_price,
            min_price=min_price,
            top_k=top_k,
        )

        if not results:
            return ToolResult(
                success=True,
                message="No matching results found in the knowledge base.",
                data={"results": [], "query": query, "search_mode": search_mode},
            )

        context = format_knowledge_context(results)
        titles = [r["title"] for r in results]

        return ToolResult(
            success=True,
            message=f"Found {len(results)} relevant items: {', '.join(titles)}",
            data={
                "results": results,
                "query": query,
                "search_mode": search_mode,
                "formatted_context": context,
            },
        )
