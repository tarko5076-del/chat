from agent.rag import search_knowledge, format_knowledge_context
from agent.tools.base import BaseTool, ToolResult


class SearchKnowledgeTool(BaseTool):
    name = "search_knowledge"
    description = (
        "Search the restaurant's knowledge base for menu items, policies, FAQs, "
        "and promotions using semantic similarity. Use this when the user asks about "
        "dishes, ingredients, allergens, restaurant rules, or current deals."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language search query",
            },
            "content_type": {
                "type": "string",
                "enum": ["menu_item", "policy", "faq", "promotion"],
                "description": "Filter by content type (optional)",
            },
            "top_k": {
                "type": "integer",
                "description": "Number of results to return (default 5)",
            },
        },
        "required": ["query"],
    }

    async def execute(self, **kwargs):
        query = kwargs.get("query", "").strip()
        if not query:
            return ToolResult(
                success=False,
                message="Please provide a search query.",
                missing_fields=["query"],
                next_action="ask_user",
            )

        content_type = kwargs.get("content_type")
        top_k = kwargs.get("top_k", 5)

        results = await search_knowledge(query, content_type=content_type, top_k=top_k)

        if not results:
            return ToolResult(
                success=True,
                message="No matching results found in the knowledge base.",
                data={"results": [], "query": query},
            )

        context = format_knowledge_context(results)
        titles = [r["title"] for r in results]

        return ToolResult(
            success=True,
            message=f"Found {len(results)} relevant items: {', '.join(titles)}",
            data={
                "results": results,
                "query": query,
                "formatted_context": context,
            },
        )