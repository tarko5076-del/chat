from typing import Any

from app.database import SessionLocal
from app.models.order import Order
from app.tools.base import BaseTool, ToolResult


class BillingTool(BaseTool):
    name = "calculate_bill"
    description = "Calculate subtotal, tax, total, and optional split amount for an order."
    parameters = {
        "type": "object",
        "properties": {
            "order_id": {"type": "integer"},
            "customer_name": {"type": "string"},
            "split_count": {"type": "integer", "minimum": 2},
        },
    }

    tax_rate = 0.0825

    async def execute(self, **kwargs: Any) -> ToolResult:
        db = SessionLocal()
        try:
            order = self._find_order(db, kwargs)
            if not order:
                return ToolResult(
                    success=False,
                    message="I could not find an active order to calculate.",
                    missing_fields=["order_id"],
                    next_action="ask_user",
                )
            subtotal = sum(item.price * item.quantity for item in order.items)
            tax = subtotal * self.tax_rate
            total = subtotal + tax
            lines = [
                f"Bill for order ID: {order.id}",
                f"Subtotal: ${subtotal:.2f}",
                f"Tax: ${tax:.2f}",
                f"Total: ${total:.2f}",
            ]
            if split_count := kwargs.get("split_count"):
                lines.append(f"Split {split_count} ways: ${total / int(split_count):.2f} each")
            return ToolResult(
                success=True,
                message="\n".join(lines),
                data={
                    "order_id": order.id,
                    "subtotal": subtotal,
                    "tax": tax,
                    "total": total,
                    "split_count": kwargs.get("split_count"),
                    "split_amount": total / int(kwargs["split_count"]) if kwargs.get("split_count") else None,
                },
                memory_updates={"order_id": order.id, "customer_name": order.customer_name},
            )
        finally:
            db.close()

    def _find_order(self, db: SessionLocal, kwargs: dict) -> Order | None:
        if order_id := kwargs.get("order_id"):
            return db.query(Order).filter(Order.id == order_id).first()
        name = kwargs.get("customer_name") or "Guest"
        return db.query(Order).filter(Order.customer_name == name, Order.status == "active").first()
