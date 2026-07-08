"""API route definitions for the chatbot application."""

from openai import OpenAIError

from fastapi import APIRouter, HTTPException, status

from app.schemas.chat import ChatRequest, ChatResponse, ErrorResponse
from app.services.llm import get_chat_response

router = APIRouter()


@router.post(
    "/chat",
    response_model=ChatResponse,
    responses={
        status.HTTP_400_BAD_REQUEST: {"model": ErrorResponse},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": ErrorResponse},
    },
)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """Receive a user message and return an AI-generated response.

    Args:
        request: The chat request containing the user's message and optional history.

    Returns:
        The assistant's response.

    Raises:
        HTTPException: If the request is invalid or an error occurs.
    """
    try:
        # Convert history to dict format if provided
        history_dicts = [{"role": msg.role, "content": msg.content} for msg in request.history] if request.history else None
        response_text = await get_chat_response(request.message, history_dicts)
        return ChatResponse(response=response_text)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    except OpenAIError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OpenRouter API error: {str(error)}",
        )
