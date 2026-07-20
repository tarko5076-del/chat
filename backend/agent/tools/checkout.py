"""Checkout tool for the AI Agent.

Takes the current cart, shows an order summary, waits for confirmation,
then creates the order and marks the cart as converted.
"""

import logging

from cart.services import CartService, CartServiceError
from orders.services import OrderService, OrderServiceError, ItemNotFoundError, ItemUnavailableError
from agent.tools.base import BaseTool, ToolResult
from config.settings import TAX_RATE, DELIVERY_FEE

logger = logging.getLogger(__name__)


class CheckoutCartTool(BaseTool):
    name = "checkout_cart"
    description = (
        "Review your cart, provide delivery and payment details, confirm, "
        "and place the order. Run this when the customer is ready to pay."
    )
    parameters = {
        "type": "object",
        "properties": {
            "customer_name": {
                "type": "string",
                "description": "Customer name for the order",
            },
            "email": {
                "type": "string",
                "description": "Customer email for order confirmation",
            },
            "phone": {
                "type": "string",
                "description": "Customer phone number",
            },
            "delivery_method": {
                "type": "string",
                "enum": ["pickup", "delivery"],
                "description": "Pickup or delivery",
            },
            "delivery_address": {
                "type": "string",
                "description": "Required if delivery_method is 'delivery'",
            },
            "payment_method": {
                "type": "string",
                "enum": ["cash", "chapa", "telebirr", "cbe_birr", "card", "mobile_money"],
                "description": "How the customer wants to pay",
            },
            "confirmed": {
                "type": "boolean",
                "description": "Set to true after the customer confirms the order summary",
            },
            "idempotency_key": {
                "type": "string",
                "description": "Unique key to prevent duplicate orders on retry",
            },
        },
    }

    def __init__(self):
        super().__init__()
        self.cart_service = CartService()
        self.order_service = OrderService()

    def execute(self, **kwargs):
        customer_id = kwargs.get("customer_id", "")
        if not customer_id:
            return ToolResult(
                success=False,
                message="Please provide your customer ID or name to proceed.",
                missing_fields=["customer_id"],
                next_action="ask_user",
            )

        cart = self.cart_service.repo.get_active_cart(customer_id)
        if not cart or not cart.items.exists():
            return ToolResult(
                success=False,
                message="Your cart is empty. Add some items first before checking out.",
                next_action="ask_user",
            )

        summary = self.cart_service.get_cart_summary(cart)

        # Check for required fields on first call
        delivery_method = kwargs.get("delivery_method", "")
        delivery_address = kwargs.get("delivery_address", "")
        payment_method = kwargs.get("payment_method", "")

        missing = []
        if not delivery_method:
            missing.append("delivery_method")
        if delivery_method == "delivery" and not delivery_address:
            missing.append("delivery_address")
        if not payment_method:
            missing.append("payment_method")

        # Confirmation gate
        if missing or not kwargs.get("confirmed"):
            return self._show_summary(summary, kwargs, missing)

        # All fields present + confirmed — create the order
        return self._place_order(cart, summary, kwargs)

    def _show_summary(
        self,
        summary: dict,
        kwargs: dict,
        missing: list[str],
    ) -> ToolResult:
        """Display order summary and ask for confirmation or missing fields."""
        delivery_method = kwargs.get("delivery_method", "")
        delivery_address = kwargs.get("delivery_address", "")

        # Calculate totals
        subtotal = float(summary["subtotal"])
        delivery_fee = DELIVERY_FEE if delivery_method == "delivery" else 0.0
        tax = subtotal * TAX_RATE
        total = subtotal + tax + delivery_fee

        lines = ["🧾 **Order Summary**", ""]
        lines.append("Items:")
        for item in summary["items"]:
            line_total = item["quantity"] * item["unit_price"]
            lines.append(
                f"  • {item['quantity']} x {item['item_name']}: "
                f"${line_total:.2f}"
            )
        lines.extend([
            "",
            f"Subtotal: ${subtotal:.2f}",
            f"Tax: ${tax:.2f}",
        ])
        if delivery_method == "delivery":
            lines.append(f"Delivery Fee: ${delivery_fee:.2f}")
        lines.append(f"**Total: ${total:.2f}**")
        lines.append("")
        if delivery_method:
            lines.append(f"Delivery: {delivery_method.title()}")
            if delivery_method == "delivery" and delivery_address:
                lines.append(f"Address: {delivery_address}")
        if kwargs.get("payment_method"):
            lines.append(f"Payment: {kwargs['payment_method'].title()}")

        if missing:
            field_labels = {
                "delivery_method": "whether you'd like pickup or delivery",
                "delivery_address": "your delivery address",
                "payment_method": "your preferred payment method",
            }
            needed = [field_labels.get(f, f) for f in missing]
            if len(needed) == 1:
                lines.append(f"\nPlease let me know {needed[0]}.")
            else:
                lines.append(
                    f"\nPlease let me know {', '.join(needed[:-1])}, "
                    f"and {needed[-1]}."
                )
        else:
            lines.append(
                "\nShall I place this order? (Reply 'yes' to confirm)"
            )

        return ToolResult(
            success=not bool(missing),
            message="\n".join(lines),
            next_action="awaiting_confirmation" if not missing else "ask_user",
            data={
                "summary": summary,
                "total": round(total, 2),
                "subtotal": round(subtotal, 2),
                "tax": round(tax, 2),
                "delivery_fee": round(delivery_fee, 2),
                "delivery_method": delivery_method,
                "delivery_address": delivery_address,
                "payment_method": kwargs.get("payment_method", ""),
                "confirmation_required": not bool(missing),
            },
        )

    def _place_order(self, cart, summary: dict, kwargs: dict) -> ToolResult:
        """Create the order and mark cart as converted."""
        customer_name = kwargs.get("customer_name", "Guest")
        customer_id = kwargs.get("customer_id", "")
        email = kwargs.get("email") or ""
        phone = kwargs.get("phone") or ""
        delivery_method = kwargs.get("delivery_method", "pickup")
        delivery_address = kwargs.get("delivery_address", "")
        payment_method = kwargs.get("payment_method", "cash")

        # Build items list from cart
        items = []
        for cart_item in cart.items.all():
            items.append({
                "menu_item_id": cart_item.menu_item_id,
                "name": cart_item.item_name,
                "quantity": cart_item.quantity,
                "price": float(cart_item.unit_price),
            })

        try:
            order = self.order_service.create_order(
                customer_name=customer_name,
                customer_id=customer_id,
                email=email,
                phone=phone,
                delivery_method=delivery_method,
                delivery_address=delivery_address,
                payment_method=payment_method,
                items=items,
                idempotency_key=kwargs.get("idempotency_key"),
            )
        except (ItemNotFoundError, ItemUnavailableError) as e:
            return ToolResult(
                success=False,
                message=str(e),
                next_action="ask_user",
            )
        except OrderServiceError as e:
            return ToolResult(
                success=False,
                message=str(e),
                next_action="ask_user",
            )

        # Mark cart as converted
        try:
            self.cart_service.checkout(customer_id, cart.id)
        except Exception:
            logger.warning("Failed to mark cart %d as converted", cart.id, exc_info=True)

        # Send confirmation email
        try:
            from agent.email_service import send_order_confirmation
            send_order_confirmation(order)
        except Exception:
            logger.debug("Failed to send order confirmation email", exc_info=True)

        # Calculate totals for response
        subtotal = float(summary["subtotal"])
        delivery_fee = DELIVERY_FEE if delivery_method == "delivery" else 0.0
        tax = subtotal * TAX_RATE
        total = subtotal + tax + delivery_fee

        return ToolResult(
            success=True,
            message=(
                f"✅ **Order placed!** Order #{order.id} has been submitted.\n\n"
                f"Total: ${total:.2f}\n"
                f"Delivery: {delivery_method.title()}\n"
                f"Payment: {payment_method.title()}\n\n"
                "Your order has been sent to the kitchen. "
                "A confirmation email has been sent."
            ),
            data={
                "order": order.to_dict(),
                "cart_id": cart.id,
            },
            memory_updates={
                "order_id": order.id,
                "customer_name": customer_name,
                "customer_id": customer_id,
                "email": email,
                "phone": phone,
                "order_status": "awaiting_payment",
                "payment_status": "pending",
                "payment_method": payment_method,
            },
        )
