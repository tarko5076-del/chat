import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_order_confirmation(order) -> bool:
    """Send order confirmation email to the customer."""
    if not order.email:
        logger.info("No email for order #%s, skipping confirmation", order.id)
        return False

    subject = f"Order #{order.id} Confirmed"
    items = order.items.all()
    items_text = "\n".join(
        f"  {item.quantity}x {item.item_name} — ${float(item.price):.2f}"
        for item in items
    )
    message = (
        f"Hi {order.customer_name or 'there'},\n\n"
        f"Your order #{order.id} has been placed successfully.\n\n"
        f"Items:\n{items_text}\n\n"
        f"Total: ${float(order.total):.2f}\n"
        f"Status: {order.status}\n\n"
        f"Thank you for your order!"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@restaurant.com"),
            recipient_list=[order.email],
            fail_silently=True,
        )
        logger.info("Order confirmation sent for order #%s to %s", order.id, order.email)
        return True
    except Exception as exc:
        logger.error("Failed to send order confirmation for order #%s: %s", order.id, exc)
        return False


def send_payment_confirmation(payment) -> bool:
    """Send payment confirmation email to the customer."""
    order = payment.order
    if not order.email:
        logger.info("No email for payment %s, skipping confirmation", payment.transaction_ref)
        return False

    subject = f"Payment Confirmed — Order #{order.id}"
    message = (
        f"Hi {order.customer_name or 'there'},\n\n"
        f"Your payment for order #{order.id} has been confirmed.\n\n"
        f"Amount: ${float(payment.amount):.2f} ({payment.currency})\n"
        f"Method: {payment.provider}\n"
        f"Reference: {payment.transaction_ref}\n\n"
        f"Thank you!"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@restaurant.com"),
            recipient_list=[order.email],
            fail_silently=True,
        )
        logger.info("Payment confirmation sent for %s to %s", payment.transaction_ref, order.email)
        return True
    except Exception as exc:
        logger.error("Failed to send payment confirmation for %s: %s", payment.transaction_ref, exc)
        return False
