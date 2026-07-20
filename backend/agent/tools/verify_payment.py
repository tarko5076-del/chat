import logging

from orders.services import OrderService, OrderNotFoundError
from payments.services import PaymentService, PaymentServiceError
from agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class VerifyPaymentTool(BaseTool):
    name = "verify_payment"
    description = (
        "Verify the payment status for an order. Checks if the payment was successful "
        "and updates the order status to paid if confirmed."
    )
    parameters = {
        "type": "object",
        "properties": {
            "order_id": {"type": "integer", "description": "The ID of the order to verify payment for."},
        },
        "required": ["order_id"],
    }

    def __init__(self):
        super().__init__()
        self.payment_service = PaymentService()
        self.order_service = OrderService()

    def execute(self, **kwargs):
        order_id = kwargs.get("order_id")
        if not order_id:
            return ToolResult(
                success=False,
                message="Missing required field: order_id.",
                missing_fields=["order_id"],
                next_action="ask_user",
            )

        try:
            order = self.order_service.get_order(int(order_id))
        except OrderNotFoundError:
            return ToolResult(
                success=False,
                message=f"I could not find order ID {order_id}.",
                missing_fields=["order_id"],
                next_action="ask_user",
            )

        if order.status == "paid":
            return ToolResult(
                success=True,
                message=(
                    "✅ Payment confirmed.\n\n"
                    "Your order has been successfully paid.\n\n"
                    "Our kitchen has started preparing your order."
                ),
                data={"order_id": order.id, "payment_status": "paid", "order_status": "paid"},
                memory_updates={
                    "payment_status": "paid",
                    "order_status": "paid",
                },
            )

        payment = self.payment_service.get_payment_by_order(order.id)
        if not payment:
            return ToolResult(
                success=False,
                message=f"No payment initiation found for Order #{order.id}.",
                data={"order_id": order.id},
                next_action="ask_user",
            )

        try:
            payment = self.payment_service.verify_and_update(payment.transaction_ref) or payment
        except PaymentServiceError as e:
            logger.warning(f"Failed to verify payment via service: {e}")

        if payment.status == "completed":
            order.status = "paid"
            order.save(update_fields=["status"])
            return ToolResult(
                success=True,
                message=(
                    "✅ Payment confirmed.\n\n"
                    "Your order has been successfully paid.\n\n"
                    "Our kitchen has started preparing your order."
                ),
                data={"order_id": order.id, "payment_status": "paid", "order_status": "paid"},
                memory_updates={
                    "payment_status": "paid",
                    "order_status": "paid",
                },
            )

        return ToolResult(
            success=False,
            message="I couldn't confirm the payment yet. It may take a minute for the payment provider to report it. I'll keep checking.",
            data={"order_id": order.id, "payment_status": "pending", "order_status": "awaiting_payment"},
            memory_updates={
                "payment_status": "pending",
                "order_status": "awaiting_payment",
            },
        )
