from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EpisodicMemory(Base):
    """Records of past interactions — events, tool traces, and outcomes.

    Each row represents a single event in a conversation: a user message,
    a tool call, a tool result, or a conversation milestone. These are
    used to recall *what happened* in previous interactions.
    """

    __tablename__ = "episodic_memory"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    event_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )
    event_data: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    tool_name: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    tool_success: Mapped[bool | None] = mapped_column(nullable=True)
    tool_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    assistant_response: Mapped[str | None] = mapped_column(Text, nullable=True)

    goal_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    goal_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    sentiment: Mapped[str | None] = mapped_column(String(20), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "conversation_id": self.conversation_id,
            "event_type": self.event_type,
            "event_data": self.event_data,
            "tool_name": self.tool_name,
            "tool_success": self.tool_success,
            "tool_duration_ms": self.tool_duration_ms,
            "user_message": self.user_message,
            "assistant_response": self.assistant_response,
            "goal_description": self.goal_description,
            "goal_status": self.goal_status,
            "sentiment": self.sentiment,
            "outcome": self.outcome,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
