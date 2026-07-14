import logging

from agent.embeddings import get_embedding
from agent.models import KnowledgeBase

logger = logging.getLogger(__name__)


async def search_knowledge(
    query: str,
    content_type: str | None = None,
    top_k: int = 5,
) -> list[dict]:
    """Search knowledge base using vector similarity.

    Returns list of dicts with title, content, content_type, score.
    """
    query_embedding = await get_embedding(query)

    qs = KnowledgeBase.objects.filter(is_active=True)

    if content_type:
        qs = qs.filter(content_type=content_type)

    # pgvector <-> operator = L2 distance
    # lower distance = more similar
    results = (
        qs.annotate(distance=KnowledgeBase.embedding.l2_distance(query_embedding))
        .order_by("distance")[:top_k]
    )

    output = []
    for item in results:
        output.append(
            {
                "title": item.title,
                "content": item.content,
                "content_type": item.content_type,
                "metadata": item.metadata,
                "distance": float(item.distance),
            }
        )

    logger.info(
        "RAG search query=%r content_type=%s top_k=%d results=%d",
        query[:80],
        content_type,
        top_k,
        len(output),
    )
    return output


def format_knowledge_context(results: list[dict]) -> str:
    """Format search results into a context block for the LLM."""
    if not results:
        return ""

    lines = ["<retrieved_knowledge>"]
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] ({r['content_type']}) {r['title']}")
        lines.append(r["content"])
        if r.get("metadata"):
            lines.append(f"  Metadata: {r['metadata']}")
        lines.append("")
    lines.append("</retrieved_knowledge>")
    return "\n".join(lines)