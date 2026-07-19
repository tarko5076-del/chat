"""Advanced RAG engine with hybrid search, metadata filtering, re-ranking, and caching.

Search modes:
  - **vector**: Pure pgvector L2 similarity search (existing behavior)
  - **keyword**: PostgreSQL full-text search via tsvector (with __icontains fallback for SQLite)
  - **hybrid** (default): Weighted fusion of vector + keyword scores with re-ranking

Metadata filtering supports: content_type, category, price range, is_active, date range.
Re-ranking applies recency boost, type-match boost, and keyword density boost.
Caching: Repeated identical queries within 60s hit an in-memory cache.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import re
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from django.db.models import Q

from agent.embeddings import EMBEDDING_DIMENSIONS, get_embedding
from agent.models import KnowledgeBase

logger = logging.getLogger(__name__)

# ── Configuration ───────────────────────────────────────────────────────

HYBRID_ALPHA = 0.7  # Weight for vector similarity (1-alpha = keyword weight)
RERANK_TOP_K = 30   # Fetch this many candidates before re-ranking
DEFAULT_TOP_K = 5
MAX_TOP_K = 20

# Scores for hybrid fusion are normalized to [0, 1].
# Anything below this threshold is discarded.
MIN_RELEVANCE_SCORE = 0.05

# ── Query cache ────────────────────────────────────────────────────────

_CACHE: OrderedDict[str, tuple[float, list[dict]]] = OrderedDict()
CACHE_MAX_SIZE = 128
CACHE_TTL_SECONDS = 60


def _cache_key(query: str, **kwargs: Any) -> str:
    """Generate a deterministic cache key from query + all filter params."""
    raw = json.dumps({"q": query.strip().lower(), **kwargs}, sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached(key: str) -> list[dict] | None:
    """Return cached results if still valid, otherwise None."""
    entry = _CACHE.get(key)
    if entry is None:
        return None
    timestamp, results = entry
    if time.monotonic() - timestamp > CACHE_TTL_SECONDS:
        del _CACHE[key]
        return None
    # Move to end (most recently used)
    _CACHE.move_to_end(key)
    return results


def _set_cache(key: str, results: list[dict]) -> None:
    """Store results in the cache, evicting oldest if full."""
    if len(_CACHE) >= CACHE_MAX_SIZE:
        _CACHE.popitem(last=False)
    _CACHE[key] = (time.monotonic(), results)


def clear_cache() -> None:
    """Clear the RAG query cache (called by knowledge management on updates)."""
    _CACHE.clear()
    logger.info("RAG query cache cleared")

# ── Helper functions ────────────────────────────────────────────────────


def _normalize_scores(values: list[float]) -> list[float]:
    """Min-max normalize a list of scores to [0, 1]."""
    if not values:
        return values
    mn, mx = min(values), max(values)
    if mx - mn < 1e-9:
        return [0.5] * len(values)
    return [(v - mn) / (mx - mn) for v in values]


def _l2_to_similarity(distances: list[float]) -> list[float]:
    """Convert L2 distances to similarity scores in [0, 1].

    Uses 1 / (1 + distance) so that distance=0 → similarity=1.
    """
    return [1.0 / (1.0 + d) for d in distances]


def _keyword_score_to_normalized(ranks: list[float]) -> list[float]:
    """Normalize PostgreSQL ts_rank values to [0, 1].

    ts_rank is roughly in [0, 1] already so this is mostly a safeguard.
    """
    return _normalize_scores(ranks) if ranks else []


def _inferred_content_type(query: str) -> str | None:
    """Try to infer the desired content type from query keywords."""
    q = query.lower()
    if any(w in q for w in ("menu", "dish", "food", "eat", "drink", "ingredient", "allergen")):
        return "menu_item"
    if any(w in q for w in ("policy", "rule", "cancel", "dress code", "opening hour", "business hour", "open", "close")):
        return "policy"
    if any(w in q for w in ("faq", "question", "common", "ask")):
        return "faq"
    if any(w in q for w in ("deal", "promo", "special", "discount", "offer", "happy hour")):
        return "promotion"
    return None


def _recency_days(item: KnowledgeBase) -> int:
    """Return days since the item was last updated (0 = today)."""
    updated = item.updated_at
    if not updated:
        return 999
    delta = datetime.now(timezone.utc) - updated
    return delta.days


# ── HybridSearchEngine ──────────────────────────────────────────────────


class HybridSearchEngine:
    """Unified search engine combining vector similarity, keyword search,
    metadata filtering, and re-ranking."""

    # ── Public API ───────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        *,
        search_mode: str = "hybrid",
        content_type: str | None = None,
        categories: list[str] | None = None,
        max_price: float | None = None,
        min_price: float | None = None,
        is_active: bool | None = True,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[dict[str, Any]]:
        """Run a search against the knowledge base.

        Args:
            query: Natural language search query.
            search_mode: ``"hybrid"`` (default), ``"vector"``, or ``"keyword"``.
            content_type: Filter by content type (menu_item, policy, faq, promotion).
            categories: Filter by metadata ``category`` values (for menu items).
            max_price: Only items with metadata ``price`` ≤ this value.
            min_price: Only items with metadata ``price`` ≥ this value.
            is_active: Filter by ``is_active`` flag (default True).
            top_k: Max results (default 5, max 20).

        Returns:
            List of dicts with keys: title, content, content_type, metadata,
            distance, score, search_mode, rank_source.
        """
        if not query.strip():
            return []

        top_k = min(max(1, top_k), MAX_TOP_K)
        rerank_k = min(RERANK_TOP_K, top_k * 4)

        # Build the base filtered queryset
        qs = self._build_queryset(
            content_type=content_type,
            categories=categories,
            max_price=max_price,
            min_price=min_price,
            is_active=is_active,
        )

        if not qs.exists():
            return []

        if search_mode == "vector":
            return self._vector_search(query, qs, top_k)
        elif search_mode == "keyword":
            return self._keyword_search(query, qs, top_k)
        else:
            return self._hybrid_search(query, qs, rerank_k, top_k)

    # ── Queryset builder ────────────────────────────────────────────────

    def _build_queryset(
        self,
        *,
        content_type: str | None = None,
        categories: list[str] | None = None,
        max_price: float | None = None,
        min_price: float | None = None,
        is_active: bool | None = True,
    ) -> KnowledgeBase.objects._QuerySet:
        """Build a filtered queryset from KnowledgeBase."""
        qs = KnowledgeBase.objects.all()

        if is_active is not None:
            qs = qs.filter(is_active=is_active)

        if content_type:
            qs = qs.filter(content_type=content_type)

        # Metadata JSONField filtering
        if categories:
            q = Q()
            for cat in categories:
                q |= Q(metadata__category__iexact=cat.strip())
            if q:
                qs = qs.filter(q)

        if max_price is not None:
            qs = qs.filter(metadata__price__lte=float(max_price))

        if min_price is not None:
            qs = qs.filter(metadata__price__gte=float(min_price))

        return qs

    # ── Vector search ───────────────────────────────────────────────────

    def _vector_search(
        self,
        query: str,
        qs: KnowledgeBase.objects._QuerySet,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Pure vector similarity search using pgvector L2 distance.

        Falls back to keyword search if pgvector is not available (e.g. SQLite).
        """
        try:
            query_embedding = get_embedding(query)
            results = (
                qs.annotate(distance=KnowledgeBase.embedding.l2_distance(query_embedding))
                .order_by("distance")[:top_k]
            )

            output = []
            distances = []
            for item in results:
                output.append(self._item_to_dict(item))
                distances.append(float(item.distance))

            similarities = _l2_to_similarity(distances)
            for i, sim in enumerate(similarities):
                output[i]["score"] = round(sim, 4)
                output[i]["score_components"] = {"vector": sim}

            return output
        except AttributeError:
            logger.debug("pgvector not available, falling back to keyword search")
            return self._keyword_search(query, qs, top_k)

    # ── Keyword search ──────────────────────────────────────────────────

    def _keyword_search(
        self,
        query: str,
        qs: KnowledgeBase.objects._QuerySet,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Keyword search using PostgreSQL full-text search with SQLite fallback."""
        terms = query.strip().split()
        if not terms:
            return []

        # Try PostgreSQL full-text search first
        results = self._try_fulltext_search(query, terms, qs, top_k)
        if results is not None:
            return results

        # Fallback: simple __icontains on title and content
        return self._icontains_search(terms, qs, top_k)

    def _try_fulltext_search(
        self,
        query: str,
        terms: list[str],
        qs: KnowledgeBase.objects._QuerySet,
        top_k: int,
    ) -> list[dict[str, Any]] | None:
        """Attempt PostgreSQL full-text search. Returns None if not available (SQLite)."""
        try:
            from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

            vector = SearchVector("title", weight="A") + SearchVector("content", weight="B")
            search_query = SearchQuery(query, config="english")

            results = (
                qs.annotate(
                    rank=SearchRank(vector, search_query),
                    search_vector=vector,
                )
                .filter(rank__gte=0.01)
                .order_by("-rank")[:top_k]
            )

            if not results:
                # Try with individual term OR logic
                q_terms = SearchQuery(terms[0], config="english")
                for term in terms[1:]:
                    q_terms = q_terms | SearchQuery(term, config="english")

                results = (
                    qs.annotate(
                        rank=SearchRank(vector, q_terms),
                    )
                    .filter(rank__gte=0.01)
                    .order_by("-rank")[:top_k]
                )

            output = []
            for item in results:
                d = self._item_to_dict(item)
                rank = float(item.rank) if hasattr(item, "rank") else 0.0
                d["score"] = round(rank, 4)
                d["score_components"] = {"keyword": rank}
                output.append(d)

            return output if output else []

        except Exception:
            logger.debug("Full-text search not available, falling back to __icontains")
            return None

    def _icontains_search(
        self,
        terms: list[str],
        qs: KnowledgeBase.objects._QuerySet,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Simple case-insensitive substring search (works with SQLite)."""
        # Score by match count: title matches score 3, content matches score 1
        scored_items: list[tuple[float, KnowledgeBase]] = []

        for item in qs:
            score = 0.0
            title_lower = item.title.lower()
            content_lower = item.content.lower()

            for term in terms:
                t = term.lower()
                if t in title_lower:
                    score += 3.0
                count = content_lower.count(t)
                if count > 0:
                    score += min(count, 5) * 1.0

            if score > 0:
                scored_items.append((score, item))

        scored_items.sort(key=lambda row: row[0], reverse=True)
        top = scored_items[:top_k]

        if not top:
            return []

        scores = [s for s, _ in top]
        normalized = _normalize_scores(scores)

        output = []
        for (score, item), norm in zip(top, normalized):
            d = self._item_to_dict(item)
            d["score"] = round(norm, 4)
            d["score_components"] = {"keyword": score}
            output.append(d)

        return output

    # ── Hybrid search (vector + keyword fusion) ─────────────────────────

    def _hybrid_search(
        self,
        query: str,
        qs: KnowledgeBase.objects._QuerySet,
        rerank_k: int,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Combined vector + keyword search with weighted fusion and re-ranking.

        Falls back to keyword search if pgvector is not available (e.g. SQLite).
        """
        try:
            query_embedding = get_embedding(query)
            alpha = HYBRID_ALPHA

            # 1. Vector search → fetch rerank_k candidates
            vector_results = (
                qs.annotate(distance=KnowledgeBase.embedding.l2_distance(query_embedding))
                .order_by("distance")[:rerank_k]
            )

            vector_map: dict[int, tuple[float, KnowledgeBase]] = {}
            for item in vector_results:
                vector_map[item.pk] = (float(item.distance), item)

            if not vector_map:
                return []

            # 2. Keyword search on the same QS → get keyword scores
            keyword_scores = self._get_keyword_scores(query, qs.filter(pk__in=list(vector_map.keys())))

            # 3. Normalize and fuse
            pks = list(vector_map.keys())
            vector_similarities = _l2_to_similarity([vector_map[pk][0] for pk in pks])

            kw_scores_list = [keyword_scores.get(pk, 0.0) for pk in pks]
            kw_normalized = _keyword_score_to_normalized(kw_scores_list)

            fused: list[tuple[float, KnowledgeBase]] = []
            for i, pk in enumerate(pks):
                _, item = vector_map[pk]
                vec_score = vector_similarities[i]
                kw_score = kw_normalized[i]
                combined = alpha * vec_score + (1.0 - alpha) * kw_score

                if combined < MIN_RELEVANCE_SCORE:
                    continue

                fused.append((combined, item, vec_score, kw_score))

            # 4. Re-rank
            fused = self._rerank(fused, query)

            # 5. Take top_k
            fused = fused[:top_k]

            output = []
            for combined, item, vec_score, kw_score in fused:
                d = self._item_to_dict(item)
                d["score"] = round(combined, 4)
                d["score_components"] = {
                    "vector": round(vec_score, 4),
                    "keyword": round(kw_score, 4),
                    "alpha": alpha,
                }
                output.append(d)

            return output
        except AttributeError:
            logger.debug("pgvector not available for hybrid search, falling back to keyword")
            return self._keyword_search(query, qs, top_k)

    def _get_keyword_scores(
        self,
        query: str,
        qs: KnowledgeBase.objects._QuerySet,
    ) -> dict[int, float]:
        """Get keyword relevance scores for items in the queryset.

        Returns dict of {pk: score}.
        """
        terms = query.strip().split()
        if not terms:
            return {}

        # Try PostgreSQL full-text search
        try:
            from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector

            vector = SearchVector("title", weight="A") + SearchVector("content", weight="B")
            q_terms = SearchQuery(terms[0], config="english")
            for term in terms[1:]:
                q_terms = q_terms | SearchQuery(term, config="english")

            ranked = (
                qs.annotate(
                    rank=SearchRank(vector, q_terms),
                )
                .filter(rank__gte=0.001)
            )

            return {item.pk: float(item.rank) for item in ranked}

        except Exception:
            pass

        # Fallback: icontains scoring
        scores: dict[int, float] = {}
        for item in qs:
            score = 0.0
            title_lower = item.title.lower()
            content_lower = item.content.lower()
            for term in terms:
                t = term.lower()
                if t in title_lower:
                    score += 3.0
                count = content_lower.count(t)
                if count > 0:
                    score += min(count, 5) * 1.0
            if score > 0:
                scores[item.pk] = score

        return scores

    # ── Re-ranking ──────────────────────────────────────────────────────

    def _rerank(
        self,
        fused: list[tuple[float, KnowledgeBase, float, float]],
        query: str,
    ) -> list[tuple[float, KnowledgeBase, float, float]]:
        """Apply re-ranking boosts to fused results.

        Boosts:
        - **Recency boost** (+10%): Items updated within 30 days.
        - **Type-match boost** (+15%): Content_type matches inferred query type.
        - **Keyword density boost** (up to +15%): Proportion of query terms in content.
        """
        query_terms = set(query.lower().split())
        inferred_type = _inferred_content_type(query)

        boosted: list[tuple[float, KnowledgeBase, float, float]] = []
        for combined, item, vec_score, kw_score in fused:
            boost = 1.0

            # Recency boost
            days = _recency_days(item)
            if days <= 30:
                boost *= 1.10

            # Type-match boost
            if inferred_type and item.content_type == inferred_type:
                boost *= 1.15

            # Keyword density boost
            if query_terms:
                title_lower = item.title.lower()
                content_lower = item.content.lower()
                matches = sum(1 for t in query_terms if t in title_lower or t in content_lower)
                density = matches / len(query_terms)
                boost *= 1.0 + (density * 0.15)

            boosted.append((combined * boost, item, vec_score, kw_score))

        boosted.sort(key=lambda row: row[0], reverse=True)
        return boosted

    # ── Output formatting ───────────────────────────────────────────────

    def _item_to_dict(self, item: KnowledgeBase) -> dict[str, Any]:
        """Convert a KnowledgeBase instance to a search result dict."""
        return {
            "id": item.id,
            "title": item.title,
            "content": item.content,
            "content_type": item.content_type,
            "metadata": item.metadata,
            "is_active": item.is_active,
            "distance": None,  # Set by search methods
            "score": None,     # Set by search methods
            "score_components": None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }


# ── Module-level convenience functions ──────────────────────────────────

_engine = HybridSearchEngine()


def search_knowledge(
    query: str,
    content_type: str | None = None,
    top_k: int = DEFAULT_TOP_K,
    use_cache: bool = True,
    **kwargs: Any,
) -> list[dict]:
    """Convenience function for backward compatibility with existing callers.

    Delegates to HybridSearchEngine.search() in hybrid mode.
    Results are cached in-memory for CACHE_TTL_SECONDS to avoid repeated
    identical queries (e.g., the same FAQ asked by multiple users).

    Args:
        query: Search query.
        content_type: Filter by content type.
        top_k: Max results.
        use_cache: Whether to use the query cache (default True).
        **kwargs: Additional keyword arguments passed to search().

    Returns:
        List of result dicts.
    """
    mode = kwargs.pop("search_mode", "hybrid")

    if use_cache:
        ck = _cache_key(query, search_mode=mode, content_type=content_type, top_k=top_k, **kwargs)
        cached = _get_cached(ck)
        if cached is not None:
            logger.debug("RAG cache hit for query=%r", query[:60])
            return cached

    results = _engine.search(
        query,
        search_mode=mode,
        content_type=content_type,
        top_k=top_k,
        **kwargs,
    )

    if use_cache:
        ck = _cache_key(query, search_mode=mode, content_type=content_type, top_k=top_k, **kwargs)
        _set_cache(ck, results)

    return results


def format_knowledge_context(results: list[dict]) -> str:
    """Format search results into a context block for the LLM.

    Same signature as the original function for backward compatibility.
    """
    if not results:
        return ""

    lines = ["<retrieved_knowledge>"]
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] ({r.get('content_type', 'unknown')}) {r.get('title', 'Untitled')}")
        lines.append(r.get("content", ""))
        if r.get("metadata"):
            lines.append(f"  Metadata: {r['metadata']}")
        if r.get("score") is not None:
            lines.append(f"  Relevance: {r['score']}")
        lines.append("")
    lines.append("</retrieved_knowledge>")
    return "\n".join(lines)
