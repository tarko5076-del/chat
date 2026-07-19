import logging

from orders.services import OrderService, OrderNotFoundError
from payments.services import (
    PaymentService,
    PaymentServiceError,
    UnsupportedPaymentMethodError,
)
from agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class PaymentTool(BaseTool):
    name = "process_payment"
    description = (
        "Process payment for a submitted order. Returns a Chapa checkout URL "
        "the customer must visit to complete payment. Supports Chapa (Telebirr, "
        "CBE Birr, bank card) and cash on delivery."
    )
    supported_methods = ["chapa", "telebirr", "cbe_birr", "cash"]
    parameters = {
        "type": "object",
        "properties": {
            "order_id": {"type": "integer"},
            "payment_method": {
                "type": "string",
                "enum": supported_methods,
                "description": "Payment method: chapa (online), telebirr, cbe_birr, or cash",
            },
            "customer_email": {
                "type": "string",
                "description": "Customer email for Chapa checkout",
            },
            "customer_name": {
                "type": "string",
                "description": "Customer name for Chapa checkout",
            },
            "confirmed": {"type": "boolean"},
            "idempotency_key": {"type": "string"},
        },
        "required": ["order_id", "payment_method", "customer_email"],
    }

    def __init__(self):
        super().__init__()
        self.payment_service = PaymentService()
        self.order_service = OrderService()

    def execute(self, **kwargs):
        missing = [
            field for field in ["order_id", "payment_method", "customer_email"]
            if not kwargs.get(field)
        ]
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
                    f"Supported payment methods are: {', '.join(self.supported_methods)}. "
                    "Chapa supports Telebirr, CBE Birr, and bank cards online."
                ),
                missing_fields=["payment_method"],
                data={"supported_methods": self.supported_methods},
                next_action="ask_user",
            )

        try:
            order = self.order_service.get_order(int(kwargs["order_id"]))
        except OrderNotFoundError:
            return ToolResult(
                success=False,
                message=f"I could not find order ID {kwargs['order_id']}.",
                missing_fields=["order_id"],
                next_action="ask_user",
            )

        if order.status == "paid":
            return ToolResult(
                success=False,
                message=f"Order #{order.id} has already been paid.",
            )

        # Confirmation gate
        if not kwargs.get("confirmed"):
            items_list = list(order.items.all())
            lines = [
                f"- {item.quantity} x ${float(item.price):.2f}"
                for item in items_list
            ]
            summary = (
                f"Order #{order.id}\n"
                f"Items:\n" + "\n".join(lines) + "\n\n"
                f"Total: ${float(order.total):.2f}\n"
                f"Payment method: {method}"
            )
            return ToolResult(
                success=False,
                message=(
                    f"{summary}\n\n"
                    "Shall I proceed with payment? I will generate a secure Chapa "
                    "checkout link for you."
                ),
                next_action="awaiting_confirmation",
                data={"confirmation_required": True, "summary": summary, "order_id": order.id},
            )

        try:
            payment, checkout_url = self.payment_service.initiate_payment(
                order=order,
                payment_method=method,
                customer_email=kwargs["customer_email"],
                customer_name=kwargs.get("customer_name", ""),
                confirmed=True,
                idempotency_key=kwargs.get("idempotency_key"),
            )
        except UnsupportedPaymentMethodError as e:
            return ToolResult(
                success=False,
                message=str(e),
                data={"supported_methods": self.supported_methods},
                missing_fields=["payment_method"],
                next_action="ask_user",
            )
        except PaymentServiceError as e:
            return ToolResult(
                success=False,
                message=str(e),
                data={"order_id": order.id, "payment_method": method},
                memory_updates={
                    "payment_method": method,
                    "payment_status": "failed",
                    "order_status": "awaiting_payment",
                },
                next_action="ask_user",
            )

        # Record business event for monitoring
        try:
            from config.monitoring import record_business_event
            record_business_event("payments")
        except ImportError:
            pass

        # Cash payment
        if method == "cash":
            return ToolResult(
                success=True,
                message=(
                    f"Cash payment recorded for Order #{order.id}. "
                    f"Total: ${float(order.total):.2f}. "
                    "Please collect cash at delivery."
                ),
                data={
                    "order_id": order.id,
                    "payment_id": payment.transaction_ref,
                    "payment_method": "cash",
                    "order_status": "paid",
                },
                memory_updates={
                    "payment_method": "cash",
                    "payment_status": "paid",
                    "payment_id": payment.transaction_ref,
                    "order_status": "paid",
                },
            )

        # Chapa online payment
        return ToolResult(
            success=True,
            message=(
                f"Payment link generated for Order #{order.id} "
                f"(${float(order.total):.2f}).\n\n"
                f"Please complete payment here: {checkout_url}\n\n"
                f"You can pay with Telebirr, CBE Birr, or bank card. "
                f"I will confirm automatically once payment is received."
            ),
            data={
                "order_id": order.id,
                "payment_id": payment.transaction_ref,
                "checkout_url": checkout_url,
                "payment_method": method,
                "confirmation_required": True,
            },
            memory_updates={
                "payment_method": method,
                "payment_status": "pending",
                "payment_id": payment.transaction_ref,
                "order_status": "awaiting_payment",
            },
        )
