import json

from asgiref.sync import async_to_sync
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
