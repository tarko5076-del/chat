from uuid import uuid4

from agent.tools.base import BaseTool, ToolResult
from config.settings import RESTAURANT_PAYMENT_PHONE
from orders.models import Order
from payments.models import Payment


class PaymentTool(BaseTool):
    name = "process_payment"
    description = "Process payment for a submitted order using a supported payment method."
    supported_methods = ["card", "mobile_money"]
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
            "confirmed": {"type": "boolean"},
            "idempotency_key": {"type": "string"},
        },
        "required": ["order_id", "payment_method"],
    }

    async def execute(self, **kwargs):
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
                    f"For mobile money, send payment to {RESTAURANT_PAYMENT_PHONE}. "
                    "Which would you like to use?"
                ),
                missing_fields=["payment_method"],
                data={"supported_methods": self.supported_methods},
                next_action="ask_user",
            )

        order = Order.objects.filter(id=int(kwargs["order_id"])).first()
        if not order:
            return ToolResult(
                success=False,
                message=f"I could not find order ID {kwargs['order_id']}.",
                missing_fields=["order_id"],
                next_action="ask_user",
            )

        idempotency_key = kwargs.get("idempotency_key")
        if idempotency_key:
            existing = Payment.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                return ToolResult(
                    success=True,
                    message=f"Payment already processed. Reference: {existing.transaction_ref}.",
                    data={
                        "order_id": order.id,
                        "payment_id": existing.transaction_ref,
                        "payment_method": existing.provider,
                        "order_status": "paid",
                    },
                    memory_updates={
                        "payment_method": existing.provider,
                        "payment_status": "paid",
                        "payment_id": existing.transaction_ref,
                        "order_status": "paid",
                    },
                )

        if not kwargs.get("confirmed"):
            items_list = list(order.items.all())
            lines = [f"- {item.quantity} x {item.item_name}: ${item.quantity * item.price:.2f}" for item in items_list]
            summary = f"Order ID: {order.id}\nItems:\n" + "\n".join(lines)
            summary += f"\n\nTotal to charge: ${float(order.total):.2f}"
            summary += f"\nPayment method: {kwargs.get('payment_method', 'Not specified')}"
            return ToolResult(
                success=False,
                message=f"{summary}\n\nPlease confirm by calling this tool again with confirmed=True to proceed with payment.",
                next_action="awaiting_confirmation",
                data={
                    "confirmation_required": True,
                    "summary": summary,
                    "order_id": order.id,
                },
            )

        if kwargs.get("simulate_failure"):
            return ToolResult(
                success=False,
                message=(
                    "The payment did not go through. You can try the same method again "
                    f"or choose another option: {self.formatted_methods()}. "
                    f"For mobile money, use {RESTAURANT_PAYMENT_PHONE}."
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
                    f"{RESTAURANT_PAYMENT_PHONE}. Once you have sent it, reply 'paid' "
                    "and I will confirm the order."
                ),
                data={
                    "order_id": order.id,
                    "payment_method": method,
                    "company_phone": RESTAURANT_PAYMENT_PHONE,
                },
                memory_updates={
                    "payment_method": method,
                    "payment_status": "pending",
                    "order_status": "awaiting_payment",
                },
                next_action="ask_user",
            )

        payment = Payment(
            order=order,
            provider=method,
            amount=order.total,
            status="completed",
            idempotency_key=idempotency_key,
        )
        payment.save()
        order.status = "paid"
        order.payment_method = method
        order.save()
        return ToolResult(
            success=True,
            message=(
                f"Payment successful via {self.display_method(method)}. "
                f"Payment reference: {payment.transaction_ref}."
            ),
            data={
                "order_id": order.id,
                "payment_id": payment.transaction_ref,
                "payment_method": method,
                "company_phone": RESTAURANT_PAYMENT_PHONE if method == "mobile_money" else None,
                "order_status": order.status,
            },
            memory_updates={
                "payment_method": method,
                "payment_status": "paid",
                "payment_id": payment.transaction_ref,
                "order_status": "paid",
            },
        )

    def formatted_methods(self):
        return "card, cash, mobile money, or gift card"

    def display_method(self, method):
        return method.replace("_", " ")
