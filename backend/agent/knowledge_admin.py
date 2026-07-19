"""Knowledge management API — CRUD for KnowledgeBase items.

Endpoints:
  GET    /agent/knowledge/              — List with filtering & search
  POST   /agent/knowledge/              — Create single item (auto-embeds)
  GET    /agent/knowledge/{id}/         — Get single item
  PUT    /agent/knowledge/{id}/         — Update item (re-embeds)
  DELETE /agent/knowledge/{id}/         — Delete item
  POST   /agent/knowledge/bulk/         — Bulk upload JSON array
  POST   /agent/knowledge/reindex/      — Re-index all items
"""

import logging

from django.db import models
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from agent.embeddings import get_embedding, get_embeddings
from agent.models import KnowledgeBase
from agent.rag import search_knowledge

logger = logging.getLogger(__name__)


class KnowledgeBaseListView(APIView):
    """List knowledge items with filtering, or create a new item."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        qs = KnowledgeBase.objects.all()

        # Filters
        content_type = request.query_params.get("content_type")
        if content_type:
            qs = qs.filter(content_type=content_type)

        is_active = request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == "true")

        search = request.query_params.get("search")
        if search:
            qs = qs.filter(
                models.Q(title__icontains=search) | models.Q(content__icontains=search)
            )

        category = request.query_params.get("category")
        if category:
            qs = qs.filter(metadata__category__iexact=category)

        # Order
        order_by = request.query_params.get("order_by", "-updated_at")
        allowed_orders = ["title", "content_type", "created_at", "updated_at",
                          "-title", "-content_type", "-created_at", "-updated_at"]
        if order_by in allowed_orders:
            qs = qs.order_by(order_by)

        limit = min(int(request.query_params.get("limit", 50)), 200)
        items = list(qs[:limit])

        return Response({
            "count": KnowledgeBase.objects.count(),
            "results": [self._item_to_dict(item) for item in items],
        })

    def post(self, request):
        """Create a new knowledge item. Auto-generates embedding."""
        title = request.data.get("title", "").strip()
        content = request.data.get("content", "").strip()
        content_type = request.data.get("content_type", "faq")
        metadata = request.data.get("metadata", {})
        is_active = request.data.get("is_active", True)

        if not title or not content:
            return Response(
                {"detail": "Title and content are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if content_type not in dict(KnowledgeBase.CONTENT_TYPES):
            return Response(
                {"detail": f"Invalid content_type. Choose from: {', '.join(dict(KnowledgeBase.CONTENT_TYPES).keys())}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate embedding
        embedding_text = f"{title}: {content}"
        embedding = get_embedding(embedding_text)

        item = KnowledgeBase.objects.create(
            content_type=content_type,
            title=title,
            content=content,
            metadata=metadata if isinstance(metadata, dict) else {},
            embedding=embedding,
            is_active=bool(is_active),
        )

        logger.info("Knowledge item created: id=%s type=%s title=%s", item.id, content_type, title)

        return Response(
            self._item_to_dict(item),
            status=status.HTTP_201_CREATED,
        )

    def _item_to_dict(self, item: KnowledgeBase) -> dict:
        return {
            "id": item.id,
            "content_type": item.content_type,
            "title": item.title,
            "content": item.content,
            "metadata": item.metadata,
            "is_active": item.is_active,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }


class KnowledgeBaseDetailView(APIView):
    """Get, update, or delete a single knowledge item."""

    permission_classes = [permissions.IsAdminUser]

    def get(self, request, item_id):
        try:
            item = KnowledgeBase.objects.get(id=item_id)
        except KnowledgeBase.DoesNotExist:
            return Response(
                {"detail": "Knowledge item not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(self._item_to_dict(item))

    def put(self, request, item_id):
        try:
            item = KnowledgeBase.objects.get(id=item_id)
        except KnowledgeBase.DoesNotExist:
            return Response(
                {"detail": "Knowledge item not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        title = request.data.get("title")
        content = request.data.get("content")
        content_type = request.data.get("content_type")
        metadata = request.data.get("metadata")
        is_active = request.data.get("is_active")

        if title is not None:
            item.title = str(title).strip()
        if content is not None:
            item.content = str(content).strip()
        if content_type is not None:
            if content_type not in dict(KnowledgeBase.CONTENT_TYPES):
                return Response(
                    {"detail": f"Invalid content_type. Choose from: {', '.join(dict(KnowledgeBase.CONTENT_TYPES).keys())}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            item.content_type = content_type
        if metadata is not None:
            item.metadata = metadata if isinstance(metadata, dict) else item.metadata
        if is_active is not None:
            item.is_active = bool(is_active)

        # Re-generate embedding
        embedding_text = f"{item.title}: {item.content}"
        item.embedding = get_embedding(embedding_text)
        item.save()

        logger.info("Knowledge item updated: id=%s", item_id)

        return Response(self._item_to_dict(item))

    def delete(self, request, item_id):
        try:
            item = KnowledgeBase.objects.get(id=item_id)
        except KnowledgeBase.DoesNotExist:
            return Response(
                {"detail": "Knowledge item not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        item.delete()
        logger.info("Knowledge item deleted: id=%s", item_id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _item_to_dict(self, item: KnowledgeBase) -> dict:
        return {
            "id": item.id,
            "content_type": item.content_type,
            "title": item.title,
            "content": item.content,
            "metadata": item.metadata,
            "is_active": item.is_active,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }


class KnowledgeBulkUploadView(APIView):
    """Bulk upload knowledge items from a JSON array."""

    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        items = request.data
        if not isinstance(items, list):
            return Response(
                {"detail": "Request body must be a JSON array of items."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created = []
        errors = []

        for i, item_data in enumerate(items):
            title = (item_data.get("title") or "").strip()
            content = (item_data.get("content") or "").strip()
            content_type = item_data.get("content_type", "faq")

            if not title or not content:
                errors.append({"index": i, "error": "Title and content are required."})
                continue

            if content_type not in dict(KnowledgeBase.CONTENT_TYPES):
                errors.append({"index": i, "error": f"Invalid content_type: {content_type}"})
                continue

            try:
                embedding_text = f"{title}: {content}"
                embedding = get_embedding(embedding_text)

                item = KnowledgeBase.objects.create(
                    content_type=content_type,
                    title=title,
                    content=content,
                    metadata=item_data.get("metadata", {}),
                    embedding=embedding,
                    is_active=bool(item_data.get("is_active", True)),
                )
                created.append(self._item_to_dict(item))
            except Exception as e:
                errors.append({"index": i, "error": str(e)})

        logger.info("Bulk upload: %d created, %d errors", len(created), len(errors))

        return Response({
            "created_count": len(created),
            "error_count": len(errors),
            "created": created,
            "errors": errors,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_400_BAD_REQUEST)

    def _item_to_dict(self, item: KnowledgeBase) -> dict:
        return {
            "id": item.id,
            "content_type": item.content_type,
            "title": item.title,
            "content": item.content,
            "metadata": item.metadata,
            "is_active": item.is_active,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }


class KnowledgeReindexView(APIView):
    """Re-index all knowledge items (re-generate embeddings)."""

    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        items = list(KnowledgeBase.objects.all())
        if not items:
            return Response(
                {"detail": "No knowledge items to re-index."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        texts = [f"{item.title}: {item.content}" for item in items]
        embeddings = get_embeddings(texts)

        updated = 0
        for item, embedding in zip(items, embeddings):
            item.embedding = embedding
            item.save(update_fields=["embedding"])
            updated += 1

        logger.info("Re-indexed %d knowledge items", updated)

        return Response({
            "detail": f"Successfully re-indexed {updated} knowledge items.",
            "count": updated,
        })
