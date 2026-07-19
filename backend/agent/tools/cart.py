"""Cart management tool for the AI Agent.

Allows the agent to add items to a cart, update quantities, remove items,
and show the current cart contents. Delegates to CartService for all
business logic and persistence.
"""

import logging
from decimal import Decimal

from cart.services import CartService, CartServiceError, CartItemNotFoundError, MenuItemNotAvailableError
from menu.services import MenuService
from agent.tools.base import BaseTool, ToolResult
from config.settings import TAX_RATE, DELIVERY_FEE

logger = logging.getLogger(__name__)


class ManageCartTool(BaseTool):
    name = "manage_cart"
    description = (
        "Add items to your shopping cart, update quantities, remove items, "
        "or show the current cart contents and total."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "update", "remove", "show"],
                "description": "What to do with the cart",
            },
            "item_name": {
                "type": "string",
                "description": "Name of the menu item to add/remove",
            },
            "menu_item_id": {
                "type": "integer",
                "description": "ID of the menu item (alternative to item_name)",
            },
            "quantity": {
                "type": "integer",
                "minimum": 1,
                "description": "Quantity to add or set (default 1)",
            },
            "notes": {
                "type": "string",
                "description": "Special instructions (e.g. 'no onions')",
            },
        },
        "required": ["action"],
    }

    def __init__(self):
        super().__init__()
        self.cart_service = CartService()
        self.menu_service = MenuService()

    def execute(self, **kwargs):
        action = kwargs.get("action", "").strip().lower()
        customer_id = kwargs.get("customer_id", "")

        if action == "show":
            return self._show_cart(customer_id)

        # For add/update/remove, we need either customer_id or customer_name
        if not customer_id:
            # We need a customer identifier; fall back to a generated one
            # if customer_name is available
            customer_name = kwargs.get("customer_name", "guest")
            customer_id = f"anon-{customer_name.lower().replace(' ', '-')}"

        try:
            if action == "add":
                return self._add_item(customer_id, kwargs)
            if action == "update":
                return self._update_quantity(customer_id, kwargs)
            if action == "remove":
                return self._remove_item(customer_id, kwargs)
        except (CartServiceError, MenuItemNotAvailableError) as e:
            return ToolResult(
                success=False,
                message=str(e),
                next_action="ask_user",
            )

        return ToolResult(
            success=False,
            message=f"Unknown cart action: {action}. Use 'add', 'update', 'remove', or 'show'.",
            next_action="ask_user",
        )

    # ── Add item ──────────────────────────────────────────────────────────

    def _add_item(self, customer_id: str, kwargs: dict) -> ToolResult:
        item_name = kwargs.get("item_name", "")
        menu_item_id = kwargs.get("menu_item_id")
        quantity = int(kwargs.get("quantity", 1))
        notes = kwargs.get("notes", "")

        # Resolve menu_item_id from item_name if needed
        if not menu_item_id and item_name:
            item = self._find_menu_item(item_name)
            if not item:
                alternatives = self.menu_service.find_alternatives(
                    requested_name=item_name, max_results=3
                )
                if alternatives:
                    alt_text = "\n".join(
                        f"- {a.name}: ${float(a.price):.2f}" for a in alternatives
                    )
                    return ToolResult(
                        success=False,
                        message=(
                            f"We don't have '{item_name}' on our menu.\n\n"
                            "Here are similar items you might enjoy:\n\n"
                            f"{alt_text}\n\n"
                            "Would you like one of these instead?"
                        ),
                        missing_fields=["item_name"],
                        data={"alternatives": [a.to_dict() for a in alternatives]},
                        next_action="ask_user",
                    )
                return ToolResult(
                    success=False,
                    message=f"We don't have '{item_name}' on our menu.",
                    missing_fields=["item_name"],
                    next_action="ask_user",
                )
            menu_item_id = item.id
        elif not menu_item_id:
            return ToolResult(
                success=False,
                message="Please specify which item to add (by name or menu_item_id).",
                missing_fields=["item_name"],
                next_action="ask_user",
            )

        try:
            cart, cart_item = self.cart_service.add_item(
                customer_id,
                menu_item_id=menu_item_id,
                quantity=quantity,
                notes=notes,
            )
        except MenuItemNotAvailableError as e:
            return ToolResult(
                success=False,
                message=str(e),
                data={"menu_item_id": menu_item_id},
                next_action="ask_user",
            )

        logger.info(
            "cart_id=%d action=add_item item=%s qty=%d",
            cart.id, cart_item.item_name, quantity,
        )

        cart_summary = self.cart_service.get_cart_summary(cart)
        return ToolResult(
            success=True,
            message=(
                f"I've added {quantity} x {cart_item.item_name} to your cart. "
                f"(Cart total: ${float(cart_summary['subtotal']):.2f})"
            ),
            data={
                "cart": cart_summary,
                "added_item": cart_item.to_dict(),
            },
            memory_updates={
                "cart_id": cart.id,
                "customer_id": customer_id,
            },
        )

    # ── Update quantity ───────────────────────────────────────────────────

    def _update_quantity(self, customer_id: str, kwargs: dict) -> ToolResult:
        cart_id = self._get_active_cart_id(customer_id)
        if not cart_id:
            return ToolResult(
                success=False,
                message="You don't have an active cart. Add an item first.",
                next_action="ask_user",
            )

        menu_item_id = self._resolve_item_id(kwargs)
        if not menu_item_id:
            return ToolResult(
                success=False,
                message="Please specify which item to update.",
                missing_fields=["item_name", "menu_item_id"],
                next_action="ask_user",
            )

        quantity = int(kwargs.get("quantity", 1))

        try:
            updated_item = self.cart_service.update_quantity(
                customer_id, cart_id, menu_item_id, quantity
            )
        except CartItemNotFoundError:
            return ToolResult(
                success=False,
                message="That item is not in your current cart.",
                next_action="ask_user",
            )

        if quantity <= 0:
            return ToolResult(
                success=True,
                message=f"I've removed {updated_item.item_name} from your cart.",
            )

        return ToolResult(
            success=True,
            message=f"I've updated {updated_item.item_name} to {quantity}.",
            data={"item": updated_item.to_dict()},
        )

    # ── Remove item ───────────────────────────────────────────────────────

    def _remove_item(self, customer_id: str, kwargs: dict) -> ToolResult:
        cart_id = self._get_active_cart_id(customer_id)
        if not cart_id:
            return ToolResult(
                success=False,
                message="You don't have an active cart.",
                next_action="ask_user",
            )

        menu_item_id = self._resolve_item_id(kwargs)
        if not menu_item_id:
            return ToolResult(
                success=False,
                message="Please specify which item to remove.",
                missing_fields=["item_name", "menu_item_id"],
                next_action="ask_user",
            )

        try:
            self.cart_service.remove_item(customer_id, cart_id, menu_item_id)
        except CartItemNotFoundError:
            return ToolResult(
                success=False,
                message="That item is not in your current cart.",
                next_action="ask_user",
            )

        return ToolResult(
            success=True,
            message="I've removed that item from your cart.",
        )

    # ── Show cart ─────────────────────────────────────────────────────────

    def _show_cart(self, customer_id: str) -> ToolResult:
        if not customer_id:
            return ToolResult(
                success=True,
                message="Your cart is empty. What would you like to order?",
                data={"cart": {"items": [], "item_count": 0, "subtotal": 0}},
            )

        cart = self.cart_service.repo.get_active_cart(customer_id)
        if not cart or not cart.items.exists():
            return ToolResult(
                success=True,
                message="Your cart is empty. What would you like to order?",
                data={"cart": {"items": [], "item_count": 0, "subtotal": 0}},
            )

        summary = self.cart_service.get_cart_summary(cart)
        lines = ["📋 Your Cart:", ""]
        for item in summary["items"]:
            notes_suffix = f" — *{item['notes']}*" if item.get("notes") else ""
            lines.append(
                f"  • {item['quantity']} x {item['item_name']}: "
                f"${float(item['line_total']):.2f}{notes_suffix}"
            )
        lines.append("")
        lines.append(f"  Subtotal: ${float(summary['subtotal']):.2f}")

        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={"cart": summary},
            memory_updates={"cart_id": cart.id},
        )

    # ── Helpers ───────────────────────────────────────────────────────────

    def _get_active_cart_id(self, customer_id: str) -> int | None:
        cart = self.cart_service.repo.get_active_cart(customer_id)
        return cart.id if cart else None

    def _find_menu_item(self, item_name: str):
        """Find a menu item by name using the menu service."""
        items = self.menu_service.list_all()
        lowered = item_name.lower()
        for item in items:
            if item.name.lower() in lowered:
                return item
        # Word-based fallback
        name_words = set(lowered.split())
        for item in items:
            item_words = set(item.name.lower().split())
            if len(name_words & item_words) >= 2:
                return item
        return None

    def _resolve_item_id(self, kwargs: dict) -> int | None:
        if kwargs.get("menu_item_id"):
            return int(kwargs["menu_item_id"])
        if item_name := kwargs.get("item_name"):
            item = self._find_menu_item(item_name)
            return item.id if item else None
        return None
