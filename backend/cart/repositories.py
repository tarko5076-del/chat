from cart.models import Cart, CartItem


class CartRepository:
    """Database access layer for Cart and CartItem models."""

    # ── Queries ───────────────────────────────────────────────────────────

    def get_by_id(self, cart_id: int, customer_id: str | None = None) -> Cart | None:
        qs = Cart.objects.prefetch_related("items")
        if customer_id:
            qs = qs.filter(customer_id=customer_id)
        return qs.filter(id=cart_id).first()

    def get_active_cart(self, customer_id: str) -> Cart | None:
        return (
            Cart.objects.prefetch_related("items")
            .filter(customer_id=customer_id, status="active")
            .first()
        )

    def list_by_customer(self, customer_id: str, *, limit: int = 20) -> list[Cart]:
        return list(
            Cart.objects.prefetch_related("items")
            .filter(customer_id=customer_id)
            .order_by("-updated_at")[:limit]
        )

    def get_item_by_menu_item(self, cart: Cart, menu_item_id: int) -> CartItem | None:
        return cart.items.filter(menu_item_id=menu_item_id).first()

    # ── Commands ──────────────────────────────────────────────────────────

    def create_cart(self, customer_id: str) -> Cart:
        cart = Cart(customer_id=customer_id, status="active")
        cart.save()
        return cart

    def add_item(
        self,
        cart: Cart,
        *,
        menu_item_id: int,
        item_name: str,
        quantity: int = 1,
        unit_price: float,
        notes: str = "",
    ) -> CartItem:
        return CartItem.objects.create(
            cart=cart,
            menu_item_id=menu_item_id,
            item_name=item_name,
            quantity=quantity,
            unit_price=unit_price,
            notes=notes,
        )

    def update_item_quantity(self, item: CartItem, quantity: int) -> CartItem:
        item.quantity = quantity
        item.save()
        return item

    def remove_item(self, item: CartItem) -> None:
        item.delete()

    def clear_cart(self, cart: Cart) -> None:
        cart.items.all().delete()

    def mark_converted(self, cart: Cart) -> None:
        Cart.objects.filter(id=cart.id).update(status="converted")
        cart.status = "converted"

    def mark_abandoned(self, cart: Cart) -> None:
        Cart.objects.filter(id=cart.id).update(status="abandoned")
        cart.status = "abandoned"
