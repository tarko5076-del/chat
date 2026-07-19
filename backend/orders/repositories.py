from django.db import transaction
from django.db.models import QuerySet

from orders.models import Order, OrderItem


class OrderRepository:
    """Database access layer for Order and OrderItem models.

    All queries are scoped to a customer_id when provided. This is the single
    point where tenant scoping / owner filtering would be added in the future.
    """

    # ── Queries ───────────────────────────────────────────────────────────

    def get_by_id(self, order_id: int, customer_id: str | None = None) -> Order | None:
        qs = Order.objects.select_related("payment").prefetch_related("items")
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        return qs.filter(id=order_id).first()

    def get_active_order(
        self,
        *,
        customer_name: str | None = None,
        customer_id: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> Order | None:
        qs = Order.objects.filter(status="active")
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        elif email:
            qs = qs.filter(email=email)
        elif phone:
            qs = qs.filter(phone=phone)
        elif customer_name and customer_name != "Guest":
            qs = qs.filter(customer_name=customer_name)
        else:
            return None
        return qs.first()

    def list_by_customer(
        self,
        customer_id: str,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[Order]:
        qs = Order.objects.filter(customer_id=customer_id).prefetch_related("items")
        if status:
            qs = qs.filter(status=status)
        return list(qs.order_by("-created_at")[:limit])

    def list_all_by_identifier(
        self,
        *,
        customer_id: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        order_id: int | None = None,
        newest_first: bool = True,
    ) -> list[Order] | None:
        """Return orders matching any provided identifier, or None if none given."""
        if order_id:
            order = self.get_by_id(order_id)
            return [order] if order else []

        qs = Order.objects.prefetch_related("items")
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        elif email:
            qs = qs.filter(email=email)
        elif phone:
            qs = qs.filter(phone=phone)
        else:
            return None

        sort = "-created_at" if newest_first else "created_at"
        return list(qs.order_by(sort, "-id"))

    def filter_by_search(self, orders: list[Order], search_terms: set[str]) -> list[Order]:
        """Filter a list of orders to those whose items contain any search term."""
        if not search_terms or not orders:
            return orders
        return [
            o
            for o in orders
            if any(
                search_terms & set(item.item_name.lower().split())
                for item in o.items.all()
            )
        ]

    def get_by_idempotency_key(self, key: str) -> Order | None:
        return Order.objects.filter(idempotency_key=key).first()

    def get_by_status(self, status: str, *, limit: int = 50) -> list[Order]:
        return list(Order.objects.filter(status=status).prefetch_related("items")[:limit])

    # ── Commands ──────────────────────────────────────────────────────────

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
        status: str = "active",
        idempotency_key: str | None = None,
    ) -> Order:
        order = Order(
            customer_name=customer_name,
            customer_id=customer_id,
            email=email,
            phone=phone,
            delivery_method=delivery_method,
            delivery_address=delivery_address,
            payment_method=payment_method,
            status=status,
            idempotency_key=idempotency_key,
        )
        order.save()
        return order

    def create_order_item(
        self,
        order: Order,
        *,
        menu_item_id: int,
        item_name: str,
        quantity: int,
        price: float,
    ) -> OrderItem:
        return OrderItem.objects.create(
            order=order,
            menu_item_id=menu_item_id,
            item_name=item_name,
            quantity=quantity,
            price=price,
        )

    def update_status(self, order: Order, status: str) -> None:
        Order.objects.filter(id=order.id).update(status=status)
        order.status = status

    def update_payment_method(self, order: Order, method: str) -> None:
        Order.objects.filter(id=order.id).update(payment_method=method)
        order.payment_method = method
