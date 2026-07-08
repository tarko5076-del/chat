"""Pydantic models for chat request and response validation."""

from pydantic import BaseModel, Field
from typing import Optional


class ChatMessage(BaseModel):
    """Represents a single message in the conversation history."""

    role: str = Field(..., description="The role of the message sender (user or assistant)")
    content: str = Field(..., description="The message content")


class ChatRequest(BaseModel):
    """Request model for the chat endpoint."""

    message: str = Field(..., min_length=1, description="The user's message")
    history: Optional[list[ChatMessage]] = Field(default_factory=list, description="Conversation history")


class ChatResponse(BaseModel):
    """Response model for the chat endpoint."""

    response: str = Field(..., description="The assistant's reply")


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str = Field(..., description="Error description")
