import logging

from agent.tools.base import BaseTool, ToolResult
from orders.models import Order
from payments.models import Payment
from payments.chapa_client import chapa_client

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
                if existing.status == "completed":
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
                elif existing.checkout_url:
                    return ToolResult(
                        success=True,
                        message=(
                            f"Payment is being processed. "
                            f"Complete payment here: {existing.checkout_url}"
                        ),
                        data={
                            "order_id": order.id,
                            "payment_id": existing.transaction_ref,
                            "checkout_url": existing.checkout_url,
                            "payment_method": existing.provider,
                            "confirmation_required": True,
                        },
                    )

        if order.status == "paid":
            return ToolResult(
                success=False,
                message=f"Order #{order.id} has already been paid.",
            )

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
                data={
                    "confirmation_required": True,
                    "summary": summary,
                    "order_id": order.id,
                },
            )

        if method == "cash":
            payment = Payment(
                order=order,
                provider="cash",
                amount=order.total,
                status="completed",
                idempotency_key=idempotency_key,
                customer_email=kwargs.get("customer_email", ""),
                customer_name=kwargs.get("customer_name", ""),
            )
            payment.save()
            order.status = "paid"
            order.payment_method = "cash"
            order.save()

            logger.info("order_id=%s payment_method=cash status=completed", order.id)

            from agent.email_service import send_payment_confirmation
            send_payment_confirmation(payment)

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

        payment = Payment(
            order=order,
            provider=method,
            amount=order.total,
            status="pending",
            idempotency_key=idempotency_key,
            customer_email=kwargs.get("customer_email", ""),
            customer_name=kwargs.get("customer_name", ""),
        )
        payment.save()

        from django.conf import settings as django_settings
        base_url = getattr(django_settings, "FRONTEND_BASE_URL", "http://localhost")
        callback_url = f"{base_url}/api/payments/webhook/chapa/"
        return_url = f"{base_url}/payment/result"

        email = kwargs["customer_email"]
        name = kwargs.get("customer_name", "Customer")
        name_parts = name.split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        init_result = chapa_client.initialize_payment(
            amount=float(order.total),
            email=email,
            first_name=first_name,
            last_name=last_name,
            tx_ref=payment.transaction_ref,
            callback_url=callback_url,
            return_url=return_url,
        )

        if init_result.success:
            payment.chapa_tx_ref = init_result.tx_ref or payment.transaction_ref
            payment.checkout_url = init_result.checkout_url or ""
            payment.status = "processing"
            payment.save(update_fields=["chapa_tx_ref", "checkout_url", "status"])

            logger.info("order_id=%s payment_method=%s tx_ref=%s status=processing", order.id, method, payment.transaction_ref)

            return ToolResult(
                success=True,
                message=(
                    f"Payment link generated for Order #{order.id} "
                    f"(${float(order.total):.2f}).\n\n"
                    f"Please complete payment here: {init_result.checkout_url}\n\n"
                    f"You can pay with Telebirr, CBE Birr, or bank card. "
                    f"I will confirm automatically once payment is received."
                ),
                data={
                    "order_id": order.id,
                    "payment_id": payment.transaction_ref,
                    "checkout_url": init_result.checkout_url,
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
        else:
            payment.status = "failed"
            payment.failure_reason = init_result.error or "Chapa init failed"
            payment.save(update_fields=["status", "failure_reason"])

            logger.warning("order_id=%s payment_method=%s status=failed error=%s", order.id, method, init_result.error)

            return ToolResult(
                success=False,
                message=(
                    f"Could not generate payment link: {init_result.error}. "
                    "Please try again or choose a different payment method."
                ),
                data={"order_id": order.id, "payment_method": method},
                memory_updates={
                    "payment_method": method,
                    "payment_status": "failed",
                    "order_status": "awaiting_payment",
                },
                next_action="ask_user",
            )
