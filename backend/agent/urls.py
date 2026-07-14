from django.urls import path

from agent.views import ChatView, ChatStreamView, CustomerMemoryView

urlpatterns = [
    path("chat/", ChatView.as_view(), name="chat"),
    path("chat/stream/", ChatStreamView.as_view(), name="chat-stream"),
    path("memory/<str:customer_id>/", CustomerMemoryView.as_view(), name="customer-memory"),
]
