from datetime import datetime

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import TAX_RATE, DELIVERY_FEE
from app.database import Base


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_name: Mapped[str] = mapped_column(String(100), nullable=False)
    customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    delivery_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        subtotal = sum(item.price * item.quantity for item in self.items)
        tax = subtotal * TAX_RATE
        delivery_fee = DELIVERY_FEE if self.delivery_method == "delivery" else 0.0
        return {
            "id": self.id,
            "customer_name": self.customer_name,
            "customer_id": self.customer_id,
            "email": self.email,
            "phone": self.phone,
            "delivery_method": self.delivery_method,
            "delivery_address": self.delivery_address,
            "payment_method": self.payment_method,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [item.to_dict() for item in self.items],
            "subtotal": subtotal,
            "tax": tax,
            "delivery_fee": delivery_fee,
            "total": subtotal + tax + delivery_fee,
        }


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(Integer, ForeignKey("orders.id"), nullable=False)
    menu_item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    item_name: Mapped[str] = mapped_column(String(100), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "menu_item_id": self.menu_item_id,
            "item_name": self.item_name,
            "quantity": self.quantity,
            "price": self.price,
        }
