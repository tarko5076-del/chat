from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.database import SessionLocal
from app.models.order import Order
from app.tools.base import BaseTool, ToolResult


class PaymentTool(BaseTool):
    name = "process_payment"
    description = "Process payment for a submitted order using a supported payment method."
    supported_methods = ["card", "cash", "mobile_money", "gift_card"]
    parameters = {
        "type": "object",
        "properties": {
            "order_id": {"type": "integer"},
            "payment_method": {
                "type": "string",
                "enum": supported_methods,
            },
            "payment_confirmed": {"type": "boolean"},
            "simulate_failure": {"type": "boolean"},
        },
        "required": ["order_id", "payment_method"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        missing = [field for field in ["order_id", "payment_method"] if not kwargs.get(field)]
        if missing:
            return ToolResult(
                success=False,
                message=f"Missing required fields: {', '.join(missing)}.",
                missing_fields=missing,
                next_action="ask_user",
            )

        method = str(kwargs["payment_method"])
        if method not in self.supported_methods:
            return ToolResult(
                success=False,
                message=(
                    f"We accept {self.formatted_methods()}. "
                    f"For mobile money, send payment to {settings.restaurant_payment_phone}. "
                    "Which would you like to use?"
                ),
                missing_fields=["payment_method"],
                data={"supported_methods": self.supported_methods},
                next_action="ask_user",
            )

        db = SessionLocal()
        try:
            order = db.query(Order).filter(Order.id == int(kwargs["order_id"])).first()
            if not order:
                return ToolResult(
                    success=False,
                    message=f"I could not find order ID {kwargs['order_id']}.",
                    missing_fields=["order_id"],
                    next_action="ask_user",
                )
            if kwargs.get("simulate_failure"):
                return ToolResult(
                    success=False,
                    message=(
                        "The payment did not go through. You can try the same method again "
                        f"or choose another option: {self.formatted_methods()}. "
                        f"For mobile money, use {settings.restaurant_payment_phone}."
                    ),
                    data={"order_id": order.id, "payment_method": method},
                    memory_updates={
                        "payment_method": method,
                        "payment_status": "failed",
                        "order_status": "awaiting_payment",
                    },
                    next_action="ask_user",
                )
            if method == "mobile_money" and not kwargs.get("payment_confirmed"):
                return ToolResult(
                    success=False,
                    message=(
                        "Please send the payment by mobile money to our company number "
                        f"{settings.restaurant_payment_phone}. Once you have sent it, reply 'paid' "
                        "and I will confirm the order."
                    ),
                    data={
                        "order_id": order.id,
                        "payment_method": method,
                        "company_phone": settings.restaurant_payment_phone,
                    },
                    memory_updates={
                        "payment_method": method,
                        "payment_status": "pending",
                        "order_status": "awaiting_payment",
                    },
                    next_action="ask_user",
                )

            payment_id = f"pay_{uuid4().hex[:12]}"
            order.status = "paid"
            order.payment_method = method
            db.commit()
            return ToolResult(
                success=True,
                message=(
                    f"Payment successful via {self.display_method(method)}. "
                    f"Payment reference: {payment_id}."
                ),
                data={
                    "order_id": order.id,
                    "payment_id": payment_id,
                    "payment_method": method,
                    "company_phone": settings.restaurant_payment_phone if method == "mobile_money" else None,
                    "order_status": order.status,
                },
                memory_updates={
                    "payment_method": method,
                    "payment_status": "paid",
                    "payment_id": payment_id,
                    "order_status": "paid",
                },
            )
        finally:
            db.close()

    def formatted_methods(self) -> str:
        return "card, cash, mobile money, or gift card"

    def display_method(self, method: str) -> str:
        return method.replace("_", " ")
