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
    customer_id: Optional[str] = Field(
        default=None,
        description="Authenticated customer identifier, when available",
    )
    customer_name: Optional[str] = Field(default=None, description="Known customer name")
    email: Optional[str] = Field(default=None, description="Known customer email address")
    phone: Optional[str] = Field(default=None, description="Known customer phone number")
    conversation_id: Optional[str] = Field(
        default=None,
        description="Server-side conversation identifier for durable memory",
    )
    history: Optional[list[ChatMessage]] = Field(default_factory=list, description="Conversation history")


class ChatResponse(BaseModel):
    """Response model for the chat endpoint."""

    response: str = Field(..., description="The assistant's reply")
    conversation_id: str = Field(..., description="Server-side conversation identifier")


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str = Field(..., description="Error description")
