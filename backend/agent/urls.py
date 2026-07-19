from django.urls import path

from agent.knowledge_admin import (
    KnowledgeBaseListView,
    KnowledgeBaseDetailView,
    KnowledgeBulkUploadView,
    KnowledgeReindexView,
)
from agent.views import (
    ChatView, ChatStreamView, CustomerMemoryView,
    CustomerProfileView, EpisodicHistoryView, MemoryFactsView,
    StaffNotificationView, ToolCallLogView,
    SessionListView, SessionDetailView,
)

urlpatterns = [
    path("chat/", ChatView.as_view(), name="chat"),
    path("chat/stream/", ChatStreamView.as_view(), name="chat-stream"),
    path("memory/<str:customer_id>/", CustomerMemoryView.as_view(), name="customer-memory"),
    path("memory/facts/", MemoryFactsView.as_view(), name="memory-facts"),
    path("memory/profile/", CustomerProfileView.as_view(), name="memory-profile"),
    path("memory/history/", EpisodicHistoryView.as_view(), name="memory-history"),
    path("staff-notifications/", StaffNotificationView.as_view(), name="staff-notifications"),
    path("staff-notifications/<int:notification_id>/", StaffNotificationView.as_view(), name="staff-notification-detail"),
    path("tool-logs/", ToolCallLogView.as_view(), name="tool-call-logs"),
    path("sessions/", SessionListView.as_view(), name="session-list"),
    path("sessions/<str:session_id>/", SessionDetailView.as_view(), name="session-detail"),
    # Knowledge management
    path("knowledge/", KnowledgeBaseListView.as_view(), name="knowledge-list"),
    path("knowledge/bulk/", KnowledgeBulkUploadView.as_view(), name="knowledge-bulk"),
    path("knowledge/reindex/", KnowledgeReindexView.as_view(), name="knowledge-reindex"),
    path("knowledge/<int:item_id>/", KnowledgeBaseDetailView.as_view(), name="knowledge-detail"),
]
