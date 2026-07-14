from django.urls import path

from agent.views import ChatView, ChatStreamView, CustomerMemoryView, StaffNotificationView, ToolCallLogView

urlpatterns = [
    path("chat/", ChatView.as_view(), name="chat"),
    path("chat/stream/", ChatStreamView.as_view(), name="chat-stream"),
    path("memory/<str:customer_id>/", CustomerMemoryView.as_view(), name="customer-memory"),
    path("staff-notifications/", StaffNotificationView.as_view(), name="staff-notifications"),
    path("staff-notifications/<int:notification_id>/", StaffNotificationView.as_view(), name="staff-notification-detail"),
    path("tool-logs/", ToolCallLogView.as_view(), name="tool-call-logs"),
]
