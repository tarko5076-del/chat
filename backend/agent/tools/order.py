import logging

from django.db import transaction

from orders.services import (
    OrderService,
    OrderServiceError,
    OrderNotFoundError,
    ItemNotFoundError,
    ItemUnavailableError,
)
from menu.services import MenuService
from agent.tools.base import BaseTool, ToolResult, TAX_RATE, DELIVERY_FEE

logger = logging.getLogger(__name__)


class OrderTool(BaseTool):
    name = "manage_order"
    description = "Create, add to, remove from, show, cancel, or retrieve customer orders."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "add", "remove", "show", "cancel", "history", "last_completed"],
            },
            "order_id": {"type": "integer"},
            "customer_id": {"type": "string"},
            "customer_name": {"type": "string"},
            "email": {"type": "string"},
            "phone": {"type": "string"},
            "item_name": {"type": "string"},
            "search": {"type": "string"},
            "delivery_method": {"type": "string", "enum": ["pickup", "delivery"]},
            "delivery_address": {"type": "string"},
            "payment_method": {
                "type": "string",
                "enum": ["card", "cash", "mobile_money", "gift_card"],
            },
            "quantity": {"type": "integer", "minimum": 1},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "menu_item_id": {"type": "integer"},
                        "name": {"type": "string"},
                        "quantity": {"type": "integer", "minimum": 1},
                        "price": {"type": "number"},
                    },
                    "required": ["menu_item_id", "name", "quantity", "price"],
                },
            },
            "confirmed": {"type": "boolean"},
            "idempotency_key": {"type": "string"},
        },
        "required": ["action"],
    }

    def __init__(self):
        super().__init__()
        self.service = OrderService()
        self.menu_service = MenuService()

    def execute(self, **kwargs):
        action = kwargs["action"]

        try:
            if action == "history":
                return self._order_history(kwargs)
            if action == "last_completed":
                return self._last_completed_order(kwargs)
            if action == "create" and kwargs.get("items"):
                return self._create_order(kwargs)
            return self._manage_existing_order(action, kwargs)
        except OrderServiceError as e:
            return ToolResult(success=False, message=str(e), next_action="ask_user")

    # ── Order creation with confirmation gate ─────────────────────────────

    def _create_order(self, kwargs):
        # Check idempotency
        idempotency_key = kwargs.get("idempotency_key")
        if idempotency_key:
            existing = self.service.repo.get_by_idempotency_key(idempotency_key)
            if existing:
                return ToolResult(
                    success=True,
                    message=f"Order already exists. ID: {existing.id}.",
                    data={"order": existing.to_dict()},
                    memory_updates={
                        "order_id": existing.id,
                        "customer_name": existing.customer_name,
                    },
                )

        missing = [
            field for field in ["customer_name", "items", "delivery_method", "payment_method"]
            if not kwargs.get(field)
        ]
        if kwargs.get("delivery_method") == "delivery" and not kwargs.get("delivery_address"):
            missing.append("delivery_address")
        if missing:
            return ToolResult(
                success=False,
                message=f"Missing required fields: {', '.join(missing)}.",
                missing_fields=missing,
                next_action="ask_user",
            )

        # Confirmation gate
        if not kwargs.get("confirmed"):
            return self._require_confirmation(kwargs)

        # Create via service
        try:
            order = self.service.create_order(
                customer_name=kwargs["customer_name"],
                customer_id=kwargs.get("customer_id"),
                email=kwargs.get("email") or "",
                phone=kwargs.get("phone") or "",
                delivery_method=kwargs.get("delivery_method", "delivery"),
                delivery_address=kwargs.get("delivery_address") or "",
                payment_method=kwargs.get("payment_method", "cash"),
                items=kwargs.get("items"),
                idempotency_key=idempotency_key,
            )
        except (ItemNotFoundError, ItemUnavailableError) as e:
            return ToolResult(success=False, message=str(e), next_action="ask_user")

        from agent.email_service import send_order_confirmation
        send_order_confirmation(order)

        return ToolResult(
            success=True,
            message=f"Order created. ID: {order.id}.",
            data={"order": order.to_dict()},
            memory_updates={
                "order_id": order.id,
                "customer_name": order.customer_name,
                "customer_id": order.customer_id,
                "email": order.email,
                "phone": order.phone,
                "order_status": "awaiting_payment",
                "payment_status": "pending",
                "payment_method": order.payment_method,
            },
        )

    # ── Existing order management ─────────────────────────────────────────

    def _manage_existing_order(self, action, kwargs):
        order = self._find_or_create_order(kwargs)
        if not order:
            return ToolResult(
                success=False,
                message="I could not find an active order.",
                missing_fields=["order_id"],
                next_action="ask_user",
            )

        if action == "create":
            return ToolResult(
                success=True,
                message=f"Order created. ID: {order.id}.",
                data={"order": order.to_dict()},
                memory_updates={"order_id": order.id, "customer_name": order.customer_name},
            )
        if action == "add":
            return self._add_item(order, kwargs)
        if action == "remove":
            return self._remove_item(order, kwargs)
        if action == "cancel":
            return self._cancel_order(order)
        return self._show_order(order)

    def _add_item(self, order, kwargs):
        try:
            item, quantity = self.service.add_item(
                order,
                kwargs.get("item_name", ""),
                quantity=int(kwargs.get("quantity", 1)),
            )
        except (ItemNotFoundError, ItemUnavailableError) as e:
            return self._item_not_found(str(e), kwargs.get("item_name", ""))

        return ToolResult(
            success=True,
            message=f"Added {quantity} x {item.name} to order ID: {order.id}.",
            data={"order": order.to_dict(), "added_item": item.name, "quantity": quantity},
            memory_updates={"order_id": order.id, "customer_name": order.customer_name},
        )

    def _remove_item(self, order, kwargs):
        try:
            item_name = self.service.remove_item(order, kwargs.get("item_name", ""))
        except ItemNotFoundError:
            return ToolResult(
                success=False,
                message="I could not find that item in the current order.",
                missing_fields=["item_name"],
                memory_updates={"order_id": order.id, "customer_name": order.customer_name},
                next_action="ask_user",
            )

        return ToolResult(
            success=True,
            message=f"Removed {item_name} from order ID: {order.id}.",
            data={"order": order.to_dict(), "removed_item": item_name},
            memory_updates={"order_id": order.id, "customer_name": order.customer_name},
        )

    def _cancel_order(self, order):
        try:
            self.service.cancel_order(order)
        except OrderServiceError as e:
            return ToolResult(
                success=False,
                message=str(e),
                data={"order": order.to_dict()},
                next_action="ask_user",
            )

        return ToolResult(
            success=True,
            message=f"Order ID: {order.id} has been cancelled.",
            data={"order": order.to_dict()},
            memory_updates={
                "order_id": None,
                "order_state": {"items": []},
                "order_status": "cancelled",
                "payment_method": None,
                "payment_status": None,
                "payment_id": None,
            },
        )

    def _show_order(self, order):
        items_list = list(order.items.all())
        if not items_list:
            return ToolResult(
                success=True,
                message=f"Order ID: {order.id} is empty.",
                data={"order": order.to_dict()},
                memory_updates={"order_id": order.id, "customer_name": order.customer_name},
            )

        lines = [f"Order ID: {order.id}"]
        for item in items_list:
            lines.append(f"- {item.quantity} x {item.item_name}: ${item.quantity * item.price:.2f}")
        lines.append(
            f"Subtotal: ${sum(item.quantity * item.price for item in items_list):.2f}"
        )
        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={"order": order.to_dict()},
            memory_updates={"order_id": order.id, "customer_name": order.customer_name},
        )

    # ── Order history ─────────────────────────────────────────────────────

    def _order_history(self, kwargs):
        try:
            orders = self.service.get_customer_orders(
                customer_id=kwargs.get("customer_id"),
                email=kwargs.get("email"),
                phone=kwargs.get("phone"),
                order_id=kwargs.get("order_id"),
                newest_first=False,
            )
        except OrderServiceError as e:
            return ToolResult(
                success=False, message=str(e),
                missing_fields=["customer_identifier"],
                next_action="ask_user",
            )

        orders = self.service.search_orders(orders, kwargs.get("search"))
        if not orders:
            return ToolResult(
                success=True,
                message="I could not find any matching previous orders.",
                data={"orders": []},
            )

        return ToolResult(
            success=True,
            message=self._format_order_history(orders),
            data={"orders": [o.to_dict() for o in orders]},
            memory_updates=self._identity_updates(kwargs),
        )

    def _last_completed_order(self, kwargs):
        try:
            order = self.service.get_last_completed_order(
                customer_id=kwargs.get("customer_id"),
                email=kwargs.get("email"),
                phone=kwargs.get("phone"),
            )
        except OrderServiceError as e:
            return ToolResult(
                success=False, message=str(e),
                missing_fields=["customer_identifier"],
                next_action="ask_user",
            )

        if not order:
            return ToolResult(
                success=True,
                message="I could not find a previous completed order for those details.",
                data={"orders": []},
            )

        return ToolResult(
            success=True,
            message=self._format_reorder_candidate(order),
            data={"order": order.to_dict()},
            memory_updates=self._identity_updates(kwargs),
        )

    # ── Helpers ───────────────────────────────────────────────────────────

    def _find_or_create_order(self, kwargs):
        order_id = kwargs.get("order_id")
        if order_id:
            try:
                return self.service.get_order(
                    order_id,
                    customer_id=kwargs.get("customer_id"),
                )
            except OrderNotFoundError:
                pass

        return self.service.get_or_create_active_order(
            customer_name=kwargs.get("customer_name", "Guest"),
            customer_id=kwargs.get("customer_id"),
            email=kwargs.get("email") or "",
            phone=kwargs.get("phone") or "",
        )

    def _require_confirmation(self, kwargs):
        items = kwargs.get("items", [])
        lines = [
            f"{item.get('quantity', 1)} x {item.get('name', 'Unknown')}"
            for item in items
        ]
        summary = "Order Summary:\n" + "\n".join(lines) if lines else "No items in this order yet."
        total_line = ""
        if items:
            subtotal = sum(
                float(item.get("price", 0)) * int(item.get("quantity", 1))
                for item in items
            )
            delivery = DELIVERY_FEE if kwargs.get("delivery_method") == "delivery" else 0.0
            total = subtotal + (subtotal * TAX_RATE) + delivery
            total_line = f"\nTotal: ${total:.2f}"

        delivery_info = f"\nDelivery method: {kwargs.get('delivery_method', 'Not specified')}"
        if kwargs.get("delivery_method") == "delivery" and kwargs.get("delivery_address"):
            delivery_info += f"\nDelivery address: {kwargs['delivery_address']}"

        return ToolResult(
            success=False,
            message=(
                f"{summary}{total_line}{delivery_info}\n\n"
                "Please confirm by calling this tool again with confirmed=True to place the order."
            ),
            next_action="awaiting_confirmation",
            data={"confirmation_required": True, "summary": f"{summary}{total_line}{delivery_info}"},
        )

    def _item_not_found(self, error_msg, requested_name):
        alternatives = self.menu_service.find_alternatives(requested_name=requested_name)
        if alternatives:
            message = (
                f"We don't currently have {requested_name} on our menu.\n\n"
                "Here are some available dishes you might enjoy:\n\n"
                f"{self._format_alternatives(alternatives)}\n\n"
                "Would you like one of these instead?"
            )
        else:
            message = f"We don't currently have {requested_name} on our menu. Would you like to see the menu?"

        return ToolResult(
            success=False,
            message=message,
            data={"requested_item": requested_name, "alternatives": [a.to_dict() for a in alternatives]},
            missing_fields=["item_name"],
            next_action="ask_user",
        )

    def _format_alternatives(self, items):
        return "\n".join(f"- {item.name}: ${item.price:.2f}" for item in items)

    def _format_order_history(self, orders):
        blocks = ["Order History"]
        for order in orders:
            blocks.append(self._format_order_block(order))
        return "\n\n".join(blocks)

    def _format_reorder_candidate(self, order):
        return (
            "I found your most recent matching order:\n\n"
            f"{self._format_order_items(order)}\n\n"
            "Would you like me to place the same order again?"
        )

    def _format_order_block(self, order):
        created = order.created_at.strftime("%d %B %Y") if order.created_at else "Unknown"
        return (
            f"Order #{order.id}\n"
            f"Date: {created}\n"
            "Items:\n"
            f"{self._format_order_items(order)}\n"
            f"Status: {order.status.title()}\n"
            f"Total: ${float(order.total):.2f}"
        )

    def _format_order_items(self, order):
        return "\n".join(f"- {item.quantity} x {item.item_name}" for item in order.items.all())

    def _identity_updates(self, kwargs):
        return {
            key: kwargs[key]
            for key in ["customer_id", "customer_name", "email", "phone"]
            if kwargs.get(key)
        }
