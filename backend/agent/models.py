from django.contrib.postgres.indexes import GinIndex
from django.db import models
from pgvector.django import VectorField


class EpisodicMemory(models.Model):
    customer_id = models.CharField(max_length=255, db_index=True)
    conversation_id = models.CharField(max_length=255, db_index=True)
    event_type = models.CharField(max_length=100)
    event_data = models.JSONField(default=dict)
    tool_name = models.CharField(max_length=100, db_index=True)
    tool_success = models.BooleanField(null=True, blank=True)
    tool_duration_ms = models.IntegerField(null=True, blank=True)
    user_message = models.TextField(null=True, blank=True)
    assistant_response = models.TextField(null=True, blank=True)
    goal_description = models.CharField(max_length=500, null=True, blank=True)
    goal_status = models.CharField(max_length=50, null=True, blank=True)
    sentiment = models.CharField(max_length=50, null=True, blank=True)
    outcome = models.CharField(max_length=100, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer_id", "conversation_id"]),
            models.Index(fields=["event_type", "created_at"]),
            models.Index(fields=["tool_name", "tool_success"]),
        ]


class SemanticMemory(models.Model):
    customer_id = models.CharField(max_length=255, db_index=True)
    category = models.CharField(max_length=100, db_index=True)
    fact_key = models.CharField(max_length=255)
    fact_value = models.TextField()
    confidence = models.FloatField(default=0.5)
    observation_count = models.IntegerField(default=1)
    source_conversation_id = models.CharField(max_length=255, null=True, blank=True)
    source_tool = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_observed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_observed_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer_id", "category", "fact_key"],
                name="unique_customer_category_fact_key",
            )
        ]
        indexes = [
            models.Index(fields=["customer_id", "category"]),
        ]


class CustomerProfile(models.Model):
    customer_id = models.CharField(max_length=255, primary_key=True)
    display_name = models.CharField(max_length=255)
    preferred_cuisine = models.CharField(max_length=255, blank=True, default="")
    dietary_restrictions = models.CharField(max_length=500, blank=True, default="")
    spice_tolerance = models.CharField(max_length=50, blank=True, default="")
    budget_range = models.CharField(max_length=100, blank=True, default="")
    favorite_items = models.TextField(blank=True, default="")
    total_orders = models.IntegerField(default=0)
    total_reservations = models.IntegerField(default=0)
    avg_spend = models.FloatField(default=0)
    last_order_at = models.DateTimeField(null=True, blank=True)
    last_reservation_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class KnowledgeBase(models.Model):
    CONTENT_TYPES = [
        ("menu_item", "Menu Item"),
        ("policy", "Restaurant Policy"),
        ("faq", "FAQ"),
        ("promotion", "Promotion"),
    ]

    content_type = models.CharField(max_length=50, choices=CONTENT_TYPES, db_index=True)
    title = models.CharField(max_length=255)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    embedding = VectorField(dimensions=1536)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["content_type", "title"]
        indexes = [
            GinIndex(fields=["embedding"], name="knowledge_embedding_idx", opclasses=["vector_l2_ops"]),
        ]


class StaffNotification(models.Model):
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("acknowledged", "Acknowledged"),
        ("resolved", "Resolved"),
    ]

    customer_id = models.CharField(max_length=255, db_index=True)
    customer_name = models.CharField(max_length=255, blank=True, default="")
    conversation_id = models.CharField(max_length=255, blank=True, default="")
    reason = models.TextField()
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="medium")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    staff_notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "priority"]),
        ]

    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "conversation_id": self.conversation_id,
            "reason": self.reason,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "staff_notes": self.staff_notes,
        }


class AgentSession(models.Model):
    user_id = models.CharField(max_length=255, db_index=True)
    title = models.CharField(max_length=255, default="New chat")
    metadata = models.JSONField(default=dict, blank=True)
    is_archived = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user_id", "is_archived"]),
            models.Index(fields=["user_id", "updated_at"]),
        ]

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "metadata": self.metadata,
            "is_archived": self.is_archived,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SessionMessage(models.Model):
    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
        ("system", "System"),
    ]

    session = models.ForeignKey(AgentSession, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, db_index=True)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["session", "created_at"]),
        ]

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
