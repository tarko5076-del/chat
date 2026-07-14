import json

from asgiref.sync import async_to_sync
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from agent.controller import agent
from agent.memory_manager import MemoryManager
from agent.memory import ConversationMemory


memory_manager = MemoryManager()


def _format_sse(event: dict) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


class ChatView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        message = request.data.get("message", "").strip()
        if not message:
            return Response(
                {"detail": "Message cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer_id = request.data.get("customer_id")
        customer_name = request.data.get("customer_name")
        email = request.data.get("email")
        phone = request.data.get("phone")
        conversation_id = request.data.get("conversation_id")
        history = request.data.get("history", [])

        memory = ConversationMemory.from_history(history)
        if customer_name:
            memory.customer_name = customer_name
        if email:
            memory.email = email
        if phone:
            memory.phone = phone

        try:
            response_text = async_to_sync(agent.run)(
                message,
                history,
                memory,
                customer_id=customer_id,
                conversation_id=conversation_id,
            )
        except ValueError as error:
            return Response(
                {"detail": str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as error:
            return Response(
                {"detail": f"Agent error: {str(error)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response({
            "response": response_text,
            "conversation_id": conversation_id,
        })


class ChatStreamView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from django.http import StreamingHttpResponse

        message = request.data.get("message", "").strip()
        if not message:
            return Response(
                {"detail": "Message cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer_id = request.data.get("customer_id")
        customer_name = request.data.get("customer_name")
        email = request.data.get("email")
        phone = request.data.get("phone")
        conversation_id = request.data.get("conversation_id")
        history = request.data.get("history", [])

        def generate():
            try:
                memory = ConversationMemory.from_history(history)
                if customer_name:
                    memory.customer_name = customer_name
                if email:
                    memory.email = email
                if phone:
                    memory.phone = phone

                import asyncio

                async def stream_events():
                    async for event in agent.run_stream(
                        message,
                        history,
                        memory,
                        customer_id=customer_id,
                        conversation_id=conversation_id,
                    ):
                        yield event

                loop = asyncio.new_event_loop()
                try:
                    agen = stream_events()
                    while True:
                        try:
                            event = loop.run_until_complete(agen.__anext__())
                            yield _format_sse(event)
                        except StopAsyncIteration:
                            break
                finally:
                    loop.close()

                yield _format_sse({"type": "conversation_id", "conversation_id": conversation_id})
                yield "data: [DONE]\n\n"
            except ValueError as error:
                yield _format_sse({"type": "error", "detail": str(error)})
                yield "data: [DONE]\n\n"
            except Exception as error:
                yield _format_sse({"type": "error", "detail": f"Agent error: {str(error)}"})
                yield "data: [DONE]\n\n"

        response = StreamingHttpResponse(
            generate(),
            content_type="text/event-stream",
        )
        response["Cache-Control"] = "no-cache"
        response["Connection"] = "keep-alive"
        response["X-Accel-Buffering"] = "no"
        return response


class CustomerMemoryView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, customer_id):
        try:
            episodic = memory_manager.get_episodic_history(customer_id=customer_id, limit=30)
            semantic = memory_manager.get_semantic_facts(customer_id=customer_id)
            profile = memory_manager.get_profile(customer_id=customer_id)

            return Response({
                "customer_id": customer_id,
                "episodic": episodic,
                "semantic": semantic,
                "profile": profile.to_dict() if profile else None,
            })
        except Exception as error:
            return Response(
                {"detail": f"Failed to load memory: {str(error)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class StaffNotificationView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        from agent.models import StaffNotification

        status_filter = request.query_params.get("status", "pending")
        notifications = StaffNotification.objects.filter(status=status_filter)[:50]
        return Response({
            "count": StaffNotification.objects.filter(status="pending").count(),
            "results": [n.to_dict() for n in notifications],
        })

    def patch(self, request, notification_id):
        from agent.models import StaffNotification

        try:
            notification = StaffNotification.objects.get(id=notification_id)
        except StaffNotification.DoesNotExist:
            return Response(
                {"detail": "Notification not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        new_status = request.data.get("status")
        staff_notes = request.data.get("staff_notes", "")

        if new_status not in ("acknowledged", "resolved"):
            return Response(
                {"detail": "Status must be 'acknowledged' or 'resolved'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        notification.status = new_status
        if staff_notes:
            notification.staff_notes = staff_notes
        if new_status == "acknowledged":
            notification.acknowledged_at = timezone.now()
        elif new_status == "resolved":
            notification.resolved_at = timezone.now()
        notification.save()

        return Response(notification.to_dict())


class ToolCallLogView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        from agent.models import EpisodicMemory

        customer_id = request.query_params.get("customer_id")
        limit = min(int(request.query_params.get("limit", 50)), 200)

        qs = EpisodicMemory.objects.filter(event_type="tool_call")
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        events = list(qs.order_by("-created_at")[:limit])

        return Response({
            "count": qs.count(),
            "results": [
                {
                    "id": e.id,
                    "tool_name": e.tool_name,
                    "success": e.tool_success,
                    "duration_ms": e.tool_duration_ms,
                    "outcome": e.outcome,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in events
            ],
        })
