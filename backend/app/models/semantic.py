from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SemanticMemory(Base):
    """Learned facts and preferences about users.

    Each row stores a single fact, preference, or pattern the agent has
    learned about a customer. Facts have a confidence score that increases
    each time the agent observes the same information, and decays over
    long periods of inactivity.
    """

    __tablename__ = "semantic_memory"
    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            "category",
            "fact_key",
            name="uq_semantic_memory_customer_fact",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    category: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )
    fact_key: Mapped[str] = mapped_column(String(100), nullable=False)
    fact_value: Mapped[str] = mapped_column(Text, nullable=False)

    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    observation_count: Mapped[int] = mapped_column(Integer, default=1)

    source_conversation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_tool: Mapped[str | None] = mapped_column(String(60), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_observed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "category": self.category,
            "fact_key": self.fact_key,
            "fact_value": self.fact_value,
            "confidence": round(self.confidence, 2),
            "observation_count": self.observation_count,
            "source_tool": self.source_tool,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_observed_at": self.last_observed_at.isoformat() if self.last_observed_at else None,
        }


class CustomerProfile(Base):
    """Aggregated customer profile built from semantic memory.

    This is a denormalized summary that provides quick access to what
    the agent knows about a customer without querying all semantic rows.
    """

    __tablename__ = "customer_profiles"

    customer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferred_cuisine: Mapped[str | None] = mapped_column(String(60), nullable=True)
    dietary_restrictions: Mapped[str | None] = mapped_column(String(200), nullable=True)
    spice_tolerance: Mapped[str | None] = mapped_column(String(20), nullable=True)
    budget_range: Mapped[str | None] = mapped_column(String(30), nullable=True)
    favorite_items: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_orders: Mapped[int] = mapped_column(Integer, default=0)
    total_reservations: Mapped[int] = mapped_column(Integer, default=0)
    avg_spend: Mapped[float] = mapped_column(Float, default=0.0)
    last_order_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_reservation_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "customer_id": self.customer_id,
            "display_name": self.display_name,
            "preferred_cuisine": self.preferred_cuisine,
            "dietary_restrictions": self.dietary_restrictions,
            "spice_tolerance": self.spice_tolerance,
            "budget_range": self.budget_range,
            "favorite_items": self.favorite_items.split(",") if self.favorite_items else [],
            "total_orders": self.total_orders,
            "total_reservations": self.total_reservations,
            "avg_spend": round(self.avg_spend, 2),
            "last_order_at": self.last_order_at.isoformat() if self.last_order_at else None,
            "last_reservation_at": self.last_reservation_at.isoformat() if self.last_reservation_at else None,
        }
