"""API route definitions for the restaurant assistant."""

import json
from typing import AsyncIterator

from openai import OpenAIError

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agent.controller import agent
from app.agent.memory_manager import MemoryManager
from app.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse, ErrorResponse
from app.services.conversations import conversation_store

router = APIRouter()

memory_manager = MemoryManager()


def _format_sse(event: dict) -> str:
    """Format an event dict as an SSE message."""
    return f"data: {json.dumps(event, default=str)}\n\n"


async def _stream_chat(
    request: ChatRequest,
    db: Session,
) -> AsyncIterator[str]:
    """Generator that yields SSE events for a chat request."""
    try:
        request_history = [
            {"role": msg.role, "content": msg.content}
            for msg in (request.history or [])
        ]
        conversation = conversation_store.get_or_create(db, request.conversation_id)
        if request_history and not conversation_store.has_messages(db, conversation.id):
            conversation_store.import_history(db, conversation, request_history)

        server_history = conversation_store.history(db, conversation)
        memory = conversation_store.memory(db, conversation)
        memory.customer_id = request.customer_id or memory.customer_id
        memory.customer_name = request.customer_name or memory.customer_name
        memory.email = request.email or memory.email
        memory.phone = request.phone or memory.phone

        full_response = ""
        async for event in agent.run_stream(
            request.message,
            server_history,
            memory,
            customer_id=memory.customer_id,
            conversation_id=conversation.id,
        ):
            if event["type"] == "done":
                full_response = event["response"]
            yield _format_sse(event)

        if full_response:
            conversation_store.append_message(db, conversation, "user", request.message)
            conversation_store.append_message(db, conversation, "assistant", full_response)
            conversation_store.update_memory(db, conversation, memory)

        yield _format_sse({"type": "conversation_id", "conversation_id": conversation.id})
        yield "data: [DONE]\n\n"

    except ValueError as error:
        yield _format_sse({"type": "error", "detail": str(error)})
        yield "data: [DONE]\n\n"
    except SQLAlchemyError as error:
        yield _format_sse({"type": "error", "detail": f"Database error: {str(error)}"})
        yield "data: [DONE]\n\n"
    except OpenAIError as error:
        yield _format_sse({"type": "error", "detail": f"LLM provider error: {str(error)}"})
        yield "data: [DONE]\n\n"


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
async def chat_endpoint(
    request: ChatRequest,
    db: Session = Depends(get_db),
) -> ChatResponse:
    """Receive a user message and return the agent's final response (non-streaming)."""
    try:
        request_history = [
            {"role": msg.role, "content": msg.content}
            for msg in (request.history or [])
        ]
        conversation = conversation_store.get_or_create(db, request.conversation_id)
        if request_history and not conversation_store.has_messages(db, conversation.id):
            conversation_store.import_history(db, conversation, request_history)

        server_history = conversation_store.history(db, conversation)
        memory = conversation_store.memory(db, conversation)
        memory.customer_id = request.customer_id or memory.customer_id
        memory.customer_name = request.customer_name or memory.customer_name
        memory.email = request.email or memory.email
        memory.phone = request.phone or memory.phone
        response_text = await agent.run(
            request.message,
            server_history,
            memory,
            customer_id=memory.customer_id,
            conversation_id=conversation.id,
        )

        conversation_store.append_message(db, conversation, "user", request.message)
        conversation_store.append_message(db, conversation, "assistant", response_text)
        conversation_store.update_memory(db, conversation, memory)

        return ChatResponse(
            response=response_text,
            conversation_id=conversation.id,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(error)}",
        )
    except OpenAIError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM provider error: {str(error)}",
        )


@router.post("/chat/stream")
async def chat_stream_endpoint(
    request: ChatRequest,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Receive a user message and stream the agent's response via SSE."""
    return StreamingResponse(
        _stream_chat(request, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/memory/{customer_id}")
async def get_customer_memory(
    customer_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """Inspect what the agent remembers about a customer."""
    episodic = memory_manager.get_episodic_history(db, customer_id=customer_id, limit=30)
    semantic = memory_manager.get_semantic_facts(db, customer_id=customer_id)
    profile = memory_manager.get_profile(db, customer_id=customer_id)

    return {
        "customer_id": customer_id,
        "episodic": episodic,
        "semantic": semantic,
        "profile": profile.to_dict() if profile else None,
    }
