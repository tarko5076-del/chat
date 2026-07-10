"""API route definitions for the restaurant assistant."""

from openai import OpenAIError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.agent.controller import agent
from app.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse, ErrorResponse
from app.services.conversations import conversation_store

router = APIRouter()


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
    """Receive a user message and return the agent's final response."""
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
        response_text = await agent.run(request.message, server_history, memory)

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
