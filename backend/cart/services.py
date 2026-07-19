import logging
from decimal import Decimal
from typing import Any

from asgiref.sync import sync_to_async

from cart.models import Cart, CartItem
from cart.repositories import CartRepository
from menu.models import MenuItem
from menu.repositories import MenuRepository

logger = logging.getLogger(__name__)


class CartServiceError(Exception):
    pass


class CartNotFoundError(CartServiceError):
    pass


class CartItemNotFoundError(CartServiceError):
    pass


class MenuItemNotAvailableError(CartServiceError):
    pass


class CartService:
    """Business logic for shopping cart management."""

    def __init__(self) -> None:
        self.repo = CartRepository()
        self.menu_repo = MenuRepository()

    # ── Read ──────────────────────────────────────────────────────────────

    def get_cart(self, cart_id: int, customer_id: str | None = None) -> Cart:
        cart = self.repo.get_by_id(cart_id, customer_id=customer_id)
        if not cart:
            raise CartNotFoundError(f"Cart #{cart_id} not found.")
        return cart

    def get_or_create_active_cart(self, customer_id: str) -> Cart:
        cart = self.repo.get_active_cart(customer_id)
        if cart:
            return cart
        return self.repo.create_cart(customer_id)

    def get_cart_summary(self, cart: Cart) -> dict[str, Any]:
        """Calculate cart totals and return a summary dict.

        Uses a fresh query (CartItem.objects.filter) instead of cart.items.all()
        to avoid stale data from Django's prefetch_related cache.
        """
        items_data = []
        subtotal = Decimal("0.00")

        for item in CartItem.objects.filter(cart=cart).only(
            "id", "menu_item_id", "item_name", "quantity", "unit_price", "notes"
        ):
            line_total = Decimal(str(item.unit_price)) * item.quantity
            subtotal += line_total
            items_data.append({
                "id": item.id,
                "menu_item_id": item.menu_item_id,
                "item_name": item.item_name,
                "quantity": item.quantity,
                "unit_price": float(item.unit_price),
                "line_total": float(line_total),
                "notes": item.notes,
            })

        return {
            "cart_id": cart.id,
            "customer_id": cart.customer_id,
            "status": cart.status,
            "items": items_data,
            "item_count": cart.items.count(),
            "subtotal": float(subtotal),
        }

    # ── Write ─────────────────────────────────────────────────────────────

    def add_item(
        self,
        customer_id: str,
        *,
        menu_item_id: int,
        quantity: int = 1,
        notes: str = "",
    ) -> tuple[Cart, CartItem]:
        """Add an item to the active cart (creating the cart if needed)."""
        item = self.menu_repo.get_by_id(menu_item_id)
        if not item:
            raise CartServiceError(f"Menu item #{menu_item_id} not found.")
        if not item.available:
            raise MenuItemNotAvailableError(f"{item.name} is currently sold out.")

        cart = self.get_or_create_active_cart(customer_id)

        existing_item = self.repo.get_item_by_menu_item(cart, menu_item_id)
        if existing_item:
            self.repo.update_item_quantity(existing_item, existing_item.quantity + quantity)
            logger.info(
                "cart_id=%d action=update_qty item=%s qty=%d",
                cart.id, item.name, existing_item.quantity,
            )
            return cart, existing_item

        cart_item = self.repo.add_item(
            cart,
            menu_item_id=item.id,
            item_name=item.name,
            quantity=quantity,
            unit_price=float(item.price),
            notes=notes,
        )
        logger.info(
            "cart_id=%d action=add_item item=%s qty=%d",
            cart.id, item.name, quantity,
        )
        return cart, cart_item

    def update_quantity(
        self,
        customer_id: str,
        cart_id: int,
        menu_item_id: int,
        quantity: int,
    ) -> CartItem:
        cart = self.get_cart(cart_id, customer_id=customer_id)
        item = self.repo.get_item_by_menu_item(cart, menu_item_id)
        if not item:
            raise CartItemNotFoundError(
                f"Menu item #{menu_item_id} not in cart #{cart_id}."
            )
        if quantity <= 0:
            self.repo.remove_item(item)
            logger.info("cart_id=%d action=remove_item item=%s", cart.id, item.item_name)
            return item
        self.repo.update_item_quantity(item, quantity)
        return item

    def remove_item(self, customer_id: str, cart_id: int, menu_item_id: int) -> None:
        cart = self.get_cart(cart_id, customer_id=customer_id)
        item = self.repo.get_item_by_menu_item(cart, menu_item_id)
        if not item:
            raise CartItemNotFoundError(
                f"Menu item #{menu_item_id} not in cart #{cart_id}."
            )
        self.repo.remove_item(item)

    def clear_cart(self, customer_id: str, cart_id: int) -> Cart:
        cart = self.get_cart(cart_id, customer_id=customer_id)
        self.repo.clear_cart(cart)
        return cart

    def checkout(self, customer_id: str, cart_id: int) -> Cart:
        """Mark a cart as converted to order (used after order creation)."""
        cart = self.get_cart(cart_id, customer_id=customer_id)
        self.repo.mark_converted(cart)
        return cart

    # ── Async helpers for agent workflow ──────────────────────────────────

    async def async_get_or_create_cart(self, customer_id: str) -> Cart:
        return await sync_to_async(self.get_or_create_active_cart)(customer_id)

    async def async_get_summary(self, cart: Cart) -> dict[str, Any]:
        return await sync_to_async(self.get_cart_summary)(cart)
