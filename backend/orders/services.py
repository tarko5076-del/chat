import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db import transaction

from menu.models import MenuItem
from menu.repositories import MenuRepository
from orders.models import Order
from orders.repositories import OrderRepository
from config.settings import TAX_RATE, DELIVERY_FEE

logger = logging.getLogger(__name__)


class OrderServiceError(Exception):
    pass


class OrderNotFoundError(OrderServiceError):
    pass


class ItemNotFoundError(OrderServiceError):
    pass


class ItemUnavailableError(OrderServiceError):
    pass


@dataclass
class OrderTotal:
    subtotal: float
    tax: float
    delivery_fee: float
    total: float


class OrderService:
    """Business logic for order management.

    All create/read/update operations go through this service,
    which delegates persistence to OrderRepository.
    """

    def __init__(self) -> None:
        self.repo = OrderRepository()
        self.menu_repo = MenuRepository()

    # ── Read ──────────────────────────────────────────────────────────────

    def get_order(self, order_id: int, customer_id: str | None = None) -> Order:
        order = self.repo.get_by_id(order_id, customer_id=customer_id)
        if not order:
            raise OrderNotFoundError(f"Order #{order_id} not found.")
        return order

    def get_active_order(
        self,
        *,
        customer_name: str | None = None,
        customer_id: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> Order | None:
        return self.repo.get_active_order(
            customer_name=customer_name,
            customer_id=customer_id,
            email=email,
            phone=phone,
        )

    def get_or_create_active_order(
        self,
        *,
        customer_name: str = "Guest",
        customer_id: str | None = None,
        email: str = "",
        phone: str = "",
    ) -> Order:
        order = self.repo.get_active_order(
            customer_name=customer_name,
            customer_id=customer_id,
            email=email,
            phone=phone,
        )
        if order:
            return order
        return self.repo.create_order(
            customer_name=customer_name,
            customer_id=customer_id,
            email=email,
            phone=phone,
        )

    def get_customer_orders(
        self,
        *,
        customer_id: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        order_id: int | None = None,
        newest_first: bool = True,
    ) -> list[Order]:
        orders = self.repo.list_all_by_identifier(
            customer_id=customer_id,
            email=email,
            phone=phone,
            order_id=order_id,
            newest_first=newest_first,
        )
        if orders is None:
            raise OrderServiceError(
                "Cannot identify customer. Provide email, phone, or order number."
            )
        return orders

    def get_last_completed_order(
        self,
        *,
        customer_id: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> Order | None:
        orders = self.repo.list_all_by_identifier(
            customer_id=customer_id,
            email=email,
            phone=phone,
            newest_first=True,
        )
        if not orders:
            return None
        for o in orders:
            if o.status in ("paid", "submitted", "completed", "delivered"):
                return o
        return None

    def calculate_total(self, order: Order) -> OrderTotal:
        subtotal = sum(item.price * item.quantity for item in order.items.all())
        delivery = Decimal(str(DELIVERY_FEE)) if order.delivery_method == "delivery" else Decimal("0")
        tax = Decimal(str(subtotal)) * Decimal(str(TAX_RATE))
        total = Decimal(str(subtotal)) + tax + delivery
        return OrderTotal(
            subtotal=float(subtotal),
            tax=float(tax),
            delivery_fee=float(delivery),
            total=float(round(total, 2)),
        )

    def search_orders(
        self,
        orders: list[Order],
        search: str | None = None,
    ) -> list[Order]:
        if not search:
            return orders
        search_terms = set(search.lower().split())
        return self.repo.filter_by_search(orders, search_terms)

    # ── Write ─────────────────────────────────────────────────────────────

    def create_order(
        self,
        *,
        customer_name: str,
        customer_id: str | None = None,
        email: str = "",
        phone: str = "",
        delivery_method: str = "delivery",
        delivery_address: str = "",
        payment_method: str = "cash",
        items: list[dict[str, Any]] | None = None,
        idempotency_key: str | None = None,
    ) -> Order:
        """Create an order with items inside a transaction."""
        # Check idempotency
        if idempotency_key:
            existing = self.repo.get_by_idempotency_key(idempotency_key)
            if existing:
                return existing

        # Verify all items exist and are available
        order_items: list[dict[str, Any]] = []
        for requested in (items or []):
            item = self._resolve_menu_item(
                menu_item_id=requested.get("menu_item_id"),
                name=requested.get("name", ""),
            )
            if not item.available:
                raise ItemUnavailableError(f"{item.name} is currently sold out.")
            order_items.append({
                "menu_item_id": item.id,
                "item_name": item.name,
                "quantity": int(requested.get("quantity", 1)),
                "price": float(item.price),
            })

        with transaction.atomic():
            order = self.repo.create_order(
                customer_name=customer_name,
                customer_id=customer_id,
                email=email,
                phone=phone,
                delivery_method=delivery_method,
                delivery_address=delivery_address,
                payment_method=payment_method,
                status="submitted",
                idempotency_key=idempotency_key,
            )
            for item in order_items:
                self.repo.create_order_item(
                    order,
                    menu_item_id=item["menu_item_id"],
                    item_name=item["item_name"],
                    quantity=item["quantity"],
                    price=item["price"],
                )

        logger.info(
            "order_id=%d action=create status=submitted items=%d total=%.2f",
            order.id,
            order.items.count(),
            float(order.total),
        )
        return order

    def add_item(
        self,
        order: Order,
        item_name: str,
        quantity: int = 1,
    ) -> tuple[MenuItem, int]:
        """Add an item to an existing order. Returns (item, new_quantity)."""
        item = self._match_menu_item(item_name)
        if not item:
            raise ItemNotFoundError(f"Item '{item_name}' not found on the menu.")
        if not item.available:
            raise ItemUnavailableError(f"{item.name} is currently sold out.")

        existing_items = list(order.items.all())
        existing_order_item = next(
            (oi for oi in existing_items if oi.menu_item_id == item.id), None
        )

        if existing_order_item:
            existing_order_item.quantity += quantity
            existing_order_item.save()
            new_qty = existing_order_item.quantity
        else:
            self.repo.create_order_item(
                order,
                menu_item_id=item.id,
                item_name=item.name,
                quantity=quantity,
                price=float(item.price),
            )
            new_qty = quantity

        logger.info("order_id=%d action=add_item item=%s qty=%d", order.id, item.name, quantity)
        return item, new_qty

    def remove_item(self, order: Order, item_query: str) -> str:
        """Remove an item from the order by name match. Returns the removed item name."""
        lowered = item_query.lower()
        items_list = list(order.items.all())
        match = next(
            (oi for oi in items_list if oi.item_name.lower() in lowered), None
        )
        if not match:
            raise ItemNotFoundError(
                f"Could not find '{item_query}' in the current order."
            )
        item_name = match.item_name
        match.delete()
        order.refresh_from_db()
        logger.info("order_id=%d action=remove_item item=%s", order.id, item_name)
        return item_name

    def cancel_order(self, order: Order) -> None:
        if order.status == "paid":
            raise OrderServiceError(
                "Order has already been paid. Please contact staff for refund."
            )
        self.repo.update_status(order, "cancelled")
        logger.info("order_id=%d action=cancel status=cancelled", order.id)

    def mark_paid(self, order: Order) -> None:
        self.repo.update_status(order, "paid")

    # ── Private helpers ───────────────────────────────────────────────────

    def _resolve_menu_item(
        self,
        menu_item_id: int | None = None,
        name: str = "",
    ) -> MenuItem:
        if menu_item_id:
            item = self.menu_repo.get_by_id(menu_item_id)
            if item:
                return item
        item = self._match_menu_item(name)
        if not item:
            raise ItemNotFoundError(f"Menu item '{name}' not found.")
        return item

    def _match_menu_item(self, query: str) -> MenuItem | None:
        """Match a natural-language query to a menu item by name."""
        items = self.menu_repo.list_all()
        lowered = query.lower()

        # Exact name match
        for item in items:
            if item.name.lower() in lowered:
                return item

        # Word-based scoring
        query_words = set(lowered.split())
        scored: list[tuple[int, int, MenuItem]] = []
        for item in items:
            name_words = set(item.name.lower().split())
            score = len(query_words & name_words)
            if score:
                scored.append((score, len(name_words), item))

        if not scored:
            return None

        scored.sort(key=lambda row: (row[0], -row[1]), reverse=True)
        best_score, _, best_item = scored[0]

        if best_score >= 2 or item.name.lower() in lowered:
            return best_item
        if best_score == 1 and len(scored) == 1:
            return best_item
        return None
