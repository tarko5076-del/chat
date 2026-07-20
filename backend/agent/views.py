import json

from asgiref.sync import async_to_sync
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from agent.controller import agent
from agent.memory_manager import MemoryManager
from agent.memory import ConversationMemory
from agent.models import AgentSession, SessionMessage
from agent.serializers import AgentSessionSerializer, AgentSessionDetailSerializer


memory_manager = MemoryManager()


class ChatStreamThrottle(AnonRateThrottle):
    rate = "15/minute"


def _format_sse(event: dict) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


def _build_memory_from_session(session, history, customer_name, email, phone, customer_id):
    """Build a ConversationMemory from session history + persisted state.

    Restores order workflow state (order_status, order_state, payment_method,
    payment_status) from session metadata so multi-step flows like quantity
    selection, delivery method, and payment method persist across requests.
    """
    memory = ConversationMemory.from_history(history)

    # Restore persisted conversational state from session metadata
    if session and session.metadata:
        mem_state = session.metadata.get("memory_state")
        if mem_state and isinstance(mem_state, dict):
            memory.order_id = mem_state.get("order_id") or memory.order_id
            memory.order_status = mem_state.get("order_status")
            memory.order_state = mem_state.get("order_state") or memory.order_state
            memory.payment_method = mem_state.get("payment_method") or memory.payment_method
            memory.payment_status = mem_state.get("payment_status")
            memory.payment_id = mem_state.get("payment_id")
            memory.reservation_id = mem_state.get("reservation_id") or memory.reservation_id
            memory.reservation_date = mem_state.get("reservation_date") or memory.reservation_date
            memory.reservation_time = mem_state.get("reservation_time") or memory.reservation_time
            memory.party_size = mem_state.get("party_size") or memory.party_size

    if customer_name:
        memory.customer_name = customer_name
    if customer_id:
        memory.customer_id = customer_id
    if email:
        memory.email = email
    if phone:
        memory.phone = phone

    return memory


def _save_memory_state(session, memory):
    """Persist conversation memory state into session metadata.

    This preserves order workflow state so it survives across requests.
    """
    state = memory.to_state()
    # Remove fields that are derivable from conversation history
    state.pop("customer_name", None)
    state.pop("customer_id", None)
    state.pop("email", None)
    state.pop("phone", None)
    session.metadata["memory_state"] = state
    session.save(update_fields=["metadata", "updated_at"])


class ChatView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ChatStreamThrottle]

    def post(self, request):
        message = request.data.get("message", "").strip()
        if not message:
            return Response(
                {"detail": "Message cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use authenticated user's ID
        customer_id = str(request.user.id)
        customer_name = request.user.username
        email = request.user.email
        phone = request.user.phone
        session_id = request.data.get("session_id")

        session = None
        conversation_id = session_id

        if session_id:
            try:
                session = AgentSession.objects.get(id=session_id, user_id=customer_id)
                history = [
                    {"role": m.role, "content": m.content}
                    for m in session.messages.all()
                ]
            except AgentSession.DoesNotExist:
                return Response(
                    {"detail": "Session not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            history = []

        memory = _build_memory_from_session(session, history, customer_name, email, phone, customer_id)

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

        if not session:
            session = AgentSession.objects.create(
                user_id=customer_id,
                title=message[:100] if len(message) > 100 else message,
            )

        SessionMessage.objects.create(session=session, role="user", content=message)
        SessionMessage.objects.create(session=session, role="assistant", content=response_text)

        if session.messages.count() <= 2:
            title = message[:100] if len(message) > 100 else message
            session.title = title
            session.save(update_fields=["title", "updated_at"])

        # Persist conversation memory state for next request
        _save_memory_state(session, memory)

        return Response({
            "response": response_text,
            "session_id": str(session.id),
            "conversation_id": str(session.id),
        })


class ChatStreamView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ChatStreamThrottle]

    def post(self, request):
        """
        Chat endpoint that uses async_to_sync (same working pattern as ChatView)
        to process the message and returns the result as SSE-formatted events
        via a simple StreamingHttpResponse generator.
        """
        from django.http import StreamingHttpResponse

        message = request.data.get("message", "").strip()
        if not message:
            return Response(
                {"detail": "Message cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        customer_id = str(request.user.id)
        customer_name = request.user.username
        email = request.user.email
        phone = request.user.phone
        session_id = request.data.get("session_id")

        session = None
        conversation_id = session_id

        if session_id:
            try:
                session = AgentSession.objects.get(id=session_id, user_id=customer_id)
                history = [
                    {"role": m.role, "content": m.content}
                    for m in session.messages.all()
                ]
            except AgentSession.DoesNotExist:
                return Response(
                    {"detail": "Session not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            history = []

        # Build memory (same pattern as ChatView)
        memory = _build_memory_from_session(session, history, customer_name, email, phone, customer_id)

        # Process via agent.run (sync wrapper around the async agent, same as ChatView)
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

        # Create/update session and messages
        if not session:
            session = AgentSession.objects.create(
                user_id=customer_id,
                title=message[:100] if len(message) > 100 else message,
            )

        SessionMessage.objects.create(session=session, role="user", content=message)
        SessionMessage.objects.create(session=session, role="assistant", content=response_text)

        if session.messages.count() <= 2:
            title = message[:100] if len(message) > 100 else message
            session.title = title
            session.save(update_fields=["title", "updated_at"])

        # Persist conversation memory state for next request
        _save_memory_state(session, memory)

        # Return a simple generator that wraps the response as SSE events
        # IMPORTANT: session_id and conversation_id MUST come BEFORE done,
        # because the frontend SSE parser returns on the 'done' event and
        # will never process events yielded after it.
        def generate():
            yield _format_sse({"type": "token", "content": response_text})
            yield _format_sse({"type": "session_id", "session_id": str(session.id)})
            yield _format_sse({"type": "conversation_id", "conversation_id": str(session.id)})
            yield _format_sse({"type": "done", "response": response_text, "steps": 0})
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


class MemoryFactsView(APIView):
    """List and manage semantic memory facts for the authenticated user."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        customer_id = str(request.user.id)
        category = request.query_params.get("category")

        facts = memory_manager.get_semantic_facts(customer_id=customer_id)

        # Optionally filter by category
        if category:
            facts = [f for f in facts if f.get("category") == category]

        return Response({
            "count": len(facts),
            "results": facts,
        })

    def delete(self, request):
        """Delete a specific semantic fact by ID."""
        customer_id = str(request.user.id)
        fact_id = request.data.get("fact_id") or request.query_params.get("fact_id")

        if fact_id:
            deleted = memory_manager.delete_semantic_fact(
                fact_id=int(fact_id),
                customer_id=customer_id,
            )
            if not deleted:
                return Response(
                    {"detail": "Fact not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response({"detail": "Fact deleted."})

        # Delete all facts if ?all=true
        if request.query_params.get("all") == "true":
            count = memory_manager.delete_all_semantic_facts(customer_id=customer_id)
            return Response({"detail": f"Deleted {count} facts."})

        return Response(
            {"detail": "Provide fact_id or ?all=true."},
            status=status.HTTP_400_BAD_REQUEST,
        )


class CustomerProfileView(APIView):
    """Get the aggregated customer profile for the authenticated user."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        customer_id = str(request.user.id)
        profile = memory_manager.get_profile(customer_id=customer_id)
        if not profile:
            return Response({"detail": "Profile not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(profile.to_dict())


class EpisodicHistoryView(APIView):
    """Get recent episodic/tool-call history for the authenticated user."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        customer_id = str(request.user.id)
        limit = min(int(request.query_params.get("limit", 50)), 200)
        events = memory_manager.get_episodic_history(
            customer_id=customer_id,
            limit=limit,
        )
        return Response({
            "count": len(events),
            "results": events,
        })


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


class SessionListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Always filter by authenticated user's ID
        user_id = request.user.id
        include_archived = request.query_params.get("include_archived", "false") == "true"

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Fetching sessions for user_id: {user_id}, user: {request.user}")

        qs = AgentSession.objects.filter(user_id=str(user_id))
        if not include_archived:
            qs = qs.filter(is_archived=False)

        sessions = list(qs.order_by("-updated_at")[:50])
        logger.info(f"Found {len(sessions)} sessions for user {user_id}")

        return Response({
            "count": qs.count(),
            "results": AgentSessionSerializer(sessions, many=True).data,
        })

    def post(self, request):
        # Use authenticated user's ID
        user_id = str(request.user.id)
        title = request.data.get("title", "New chat")

        session = AgentSession.objects.create(user_id=user_id, title=title)
        return Response(
            AgentSessionSerializer(session).data,
            status=status.HTTP_201_CREATED,
        )


class SessionDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, session_id):
        try:
            session = AgentSession.objects.get(id=session_id)
        except AgentSession.DoesNotExist:
            return Response(
                {"detail": "Session not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(AgentSessionDetailSerializer(session).data)

    def patch(self, request, session_id):
        try:
            session = AgentSession.objects.get(id=session_id)
        except AgentSession.DoesNotExist:
            return Response(
                {"detail": "Session not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        title = request.data.get("title")
        is_archived = request.data.get("is_archived")

        if title is not None:
            session.title = title
        if is_archived is not None:
            session.is_archived = is_archived
        session.save()

        return Response(AgentSessionSerializer(session).data)

    def delete(self, request, session_id):
        try:
            session = AgentSession.objects.get(id=session_id)
        except AgentSession.DoesNotExist:
            return Response(
                {"detail": "Session not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        session.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
