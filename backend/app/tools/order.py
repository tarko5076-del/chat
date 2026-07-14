import re
from typing import Any

from app.core.config import TAX_RATE, DELIVERY_FEE
from app.database import SessionLocal
from app.models.menu import MenuItem
from app.models.order import Order, OrderItem
from app.tools.base import BaseTool, ToolResult
from app.utils.text import words as _words, cuisine_hint_words as _cuisine_hint_words


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
        },
        "required": ["action"],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        db = SessionLocal()
        try:
            action = kwargs["action"]
            if action == "history":
                return self._order_history(db, kwargs)
            if action == "last_completed":
                return self._last_completed_order(db, kwargs)
            if action == "create" and kwargs.get("items"):
                return self._create_order(db, kwargs)
            order = self._find_or_create_order(db, kwargs)
            if action == "create":
                return ToolResult(
                    success=True,
                    message=f"Order created. ID: {order.id}.",
                    data={"order": order.to_dict()},
                    memory_updates={"order_id": order.id, "customer_name": order.customer_name},
                )
            if action == "add":
                return self._add_item(db, order, kwargs)
            if action == "remove":
                return self._remove_item(db, order, kwargs)
            if action == "cancel":
                return self._cancel_order(db, order)
            return self._show_order(order)
        finally:
            db.close()

    def _create_order(self, db: SessionLocal, kwargs: dict) -> ToolResult:
        missing = [field for field in ["customer_name", "items", "delivery_method", "payment_method"] if not kwargs.get(field)]
        if kwargs.get("delivery_method") == "delivery" and not kwargs.get("delivery_address"):
            missing.append("delivery_address")
        if missing:
            return ToolResult(
                success=False,
                message=f"Missing required fields: {', '.join(missing)}.",
                missing_fields=missing,
                next_action="ask_user",
            )

        order_items: list[dict[str, Any]] = []
        for requested in kwargs["items"]:
            item = self._menu_item_by_id_or_name(
                db,
                requested.get("menu_item_id"),
                requested.get("name", ""),
            )
            if not item:
                return self._item_not_found(db, requested.get("name", "that item"))
            if not item.available:
                return self._item_unavailable(db, item)
            order_items.append(
                {
                    "menu_item_id": item.id,
                    "name": item.name,
                    "quantity": int(requested.get("quantity") or 1),
                    "price": float(item.price),
                }
            )

        order = Order(
            customer_name=kwargs["customer_name"],
            customer_id=kwargs.get("customer_id"),
            email=kwargs.get("email"),
            phone=kwargs.get("phone"),
            delivery_method=kwargs.get("delivery_method"),
            delivery_address=kwargs.get("delivery_address"),
            payment_method=kwargs.get("payment_method"),
            status="submitted",
        )
        db.add(order)
        db.flush()
        for item in order_items:
            db.add(
                OrderItem(
                    order_id=order.id,
                    menu_item_id=item["menu_item_id"],
                    item_name=item["name"],
                    quantity=int(item["quantity"]),
                    price=float(item["price"]),
                )
            )
        db.commit()
        db.refresh(order)
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

    def _find_or_create_order(self, db: SessionLocal, kwargs: dict) -> Order:
        if order_id := kwargs.get("order_id"):
            order = db.query(Order).filter(Order.id == order_id).first()
            if order:
                return order
        name = kwargs.get("customer_name") or "Guest"
        query = db.query(Order).filter(Order.status == "active")
        if kwargs.get("customer_id"):
            query = query.filter(Order.customer_id == kwargs["customer_id"])
        elif kwargs.get("email"):
            query = query.filter(Order.email == kwargs["email"])
        elif kwargs.get("phone"):
            query = query.filter(Order.phone == kwargs["phone"])
        else:
            query = query.filter(Order.customer_name == name)
        order = query.first()
        if order:
            return order
        order = Order(
            customer_name=name,
            customer_id=kwargs.get("customer_id"),
            email=kwargs.get("email"),
            phone=kwargs.get("phone"),
        )
        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    def _add_item(self, db: SessionLocal, order: Order, kwargs: dict) -> ToolResult:
        item = self._match_menu_item(db, kwargs.get("item_name", ""))
        if not item:
            return self._item_not_found(db, kwargs.get("item_name", "that item"))
        if not item.available:
            return self._item_unavailable(db, item)
        quantity = int(kwargs.get("quantity") or 1)
        existing = next((line for line in order.items if line.menu_item_id == item.id), None)
        if existing:
            existing.quantity += quantity
        else:
            db.add(
                OrderItem(
                    order_id=order.id,
                    menu_item_id=item.id,
                    item_name=item.name,
                    quantity=quantity,
                    price=item.price,
                )
            )
        db.commit()
        db.refresh(order)
        return ToolResult(
            success=True,
            message=f"Added {quantity} x {item.name} to order ID: {order.id}.",
            data={"order": order.to_dict(), "added_item": item.name, "quantity": quantity},
            memory_updates={"order_id": order.id, "customer_name": order.customer_name},
        )

    def _remove_item(self, db: SessionLocal, order: Order, kwargs: dict) -> ToolResult:
        query = kwargs.get("item_name", "").lower()
        item = next((line for line in order.items if line.item_name.lower() in query), None)
        if not item:
            return ToolResult(
                success=False,
                message="I could not find that item in the current order.",
                missing_fields=["item_name"],
                memory_updates={"order_id": order.id, "customer_name": order.customer_name},
                next_action="ask_user",
            )
        item_name = item.item_name
        db.delete(item)
        db.commit()
        db.refresh(order)
        return ToolResult(
            success=True,
            message=f"Removed {item_name} from order ID: {order.id}.",
            data={"order": order.to_dict(), "removed_item": item_name},
            memory_updates={"order_id": order.id, "customer_name": order.customer_name},
        )

    def _cancel_order(self, db: SessionLocal, order: Order) -> ToolResult:
        if order.status == "paid":
            return ToolResult(
                success=False,
                message=(
                    f"Order ID: {order.id} has already been paid. "
                    "Please contact the restaurant team for refund or cancellation help."
                ),
                data={"order": order.to_dict()},
                memory_updates={"order_status": order.status},
                next_action="ask_user",
            )
        order.status = "cancelled"
        db.commit()
        db.refresh(order)
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

    def _show_order(self, order: Order) -> ToolResult:
        if not order.items:
            return ToolResult(
                success=True,
                message=f"Order ID: {order.id} is empty.",
                data={"order": order.to_dict()},
                memory_updates={"order_id": order.id, "customer_name": order.customer_name},
            )
        lines = [f"Order ID: {order.id}"]
        for item in order.items:
            lines.append(f"- {item.quantity} x {item.item_name}: ${item.quantity * item.price:.2f}")
        lines.append(f"Subtotal: ${sum(item.quantity * item.price for item in order.items):.2f}")
        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={"order": order.to_dict()},
            memory_updates={"order_id": order.id, "customer_name": order.customer_name},
        )

    def _match_menu_item(self, db: SessionLocal, query: str) -> MenuItem | None:
        items = db.query(MenuItem).all()
        lowered = query.lower()
        exact = next((item for item in items if item.name.lower() in lowered), None)
        if exact:
            return exact
        query_words = _words(lowered)
        scored = []
        for item in items:
            name_words = _words(item.name)
            score = len(query_words & name_words)
            if score:
                scored.append((score, len(name_words), item))
        if not scored:
            return None
        scored.sort(key=lambda row: (row[0], -row[1]), reverse=True)
        score, _, item = scored[0]
        return item if score >= 2 or item.name.lower() in lowered or (score == 1 and len(scored) == 1) else None

    def _menu_item_by_id_or_name(
        self,
        db: SessionLocal,
        menu_item_id: int | None,
        name: str,
    ) -> MenuItem | None:
        if menu_item_id:
            item = db.query(MenuItem).filter(MenuItem.id == int(menu_item_id)).first()
            if item:
                return item
        return self._match_menu_item(db, name)

    def _order_history(self, db: SessionLocal, kwargs: dict) -> ToolResult:
        orders_result = self._customer_orders(db, kwargs, newest_first=False)
        if isinstance(orders_result, ToolResult):
            return orders_result
        orders = self._filter_orders(orders_result, kwargs.get("search"))
        if not orders:
            return ToolResult(
                success=True,
                message="I could not find any matching previous orders for those details.",
                data={"orders": []},
            )
        return ToolResult(
            success=True,
            message=self._format_order_history(orders),
            data={"orders": [order.to_dict() for order in orders]},
            memory_updates=self._identity_updates(kwargs),
        )

    def _last_completed_order(self, db: SessionLocal, kwargs: dict) -> ToolResult:
        orders_result = self._customer_orders(db, kwargs, newest_first=True)
        if isinstance(orders_result, ToolResult):
            return orders_result
        orders = [
            order
            for order in self._filter_orders(orders_result, kwargs.get("search"))
            if order.status in {"paid", "submitted", "completed", "delivered"}
        ]
        if not orders:
            return ToolResult(
                success=True,
                message="I could not find a previous completed order for those details.",
                data={"orders": []},
            )
        order = orders[0]
        return ToolResult(
            success=True,
            message=self._format_reorder_candidate(order),
            data={"order": order.to_dict()},
            memory_updates=self._identity_updates(kwargs),
        )

    def _customer_orders(
        self,
        db: SessionLocal,
        kwargs: dict,
        newest_first: bool,
    ) -> list[Order] | ToolResult:
        query = db.query(Order)
        if kwargs.get("customer_id"):
            query = query.filter(Order.customer_id == kwargs["customer_id"])
        elif kwargs.get("email"):
            query = query.filter(Order.email == kwargs["email"])
        elif kwargs.get("phone"):
            query = query.filter(Order.phone == kwargs["phone"])
        elif kwargs.get("order_id"):
            query = query.filter(Order.id == int(kwargs["order_id"]))
        else:
            return ToolResult(
                success=False,
                message=(
                    "I can show previous orders once I can identify the customer. "
                    "Please provide the email address, phone number, or order number used for the order."
                ),
                missing_fields=["customer_identifier"],
                next_action="ask_user",
            )
        sort_column = Order.created_at.desc() if newest_first else Order.created_at.asc()
        return query.order_by(sort_column, Order.id.desc() if newest_first else Order.id.asc()).all()

    def _filter_orders(self, orders: list[Order], search: str | None) -> list[Order]:
        if not search:
            return orders
        search_words = _words(search)
        if not search_words:
            return orders
        return [
            order
            for order in orders
            if any(search_words & _words(item.item_name) for item in order.items)
        ]

    def _item_not_found(self, db: SessionLocal, requested_name: str) -> ToolResult:
        alternatives = self._alternatives(db, requested_name=requested_name)
        if alternatives:
            message = (
                f"We don't currently have {requested_name} on our menu.\n\n"
                "Here are some available dishes you might enjoy:\n\n"
                f"{self._format_alternatives(alternatives)}\n\n"
                "Would you like one of these instead?"
            )
        else:
            message = (
                f"We don't currently have {requested_name} on our menu. "
                "Would you like to see the menu?"
            )
        return ToolResult(
            success=False,
            message=message,
            data={"requested_item": requested_name, "alternatives": [item.to_dict() for item in alternatives]},
            missing_fields=["item_name"],
            next_action="ask_user",
        )

    def _item_unavailable(self, db: SessionLocal, item: MenuItem) -> ToolResult:
        alternatives = self._alternatives(db, item=item)
        message = (
            f"I'm sorry, {item.name} is currently sold out.\n\n"
            "Here are some similar dishes that are available:\n\n"
            f"{self._format_alternatives(alternatives)}\n\n"
            "Would you like one of these instead?"
        )
        return ToolResult(
            success=False,
            message=message,
            data={"requested_item": item.to_dict(), "alternatives": [alt.to_dict() for alt in alternatives]},
            next_action="ask_user",
        )

    def _alternatives(
        self,
        db: SessionLocal,
        requested_name: str | None = None,
        item: MenuItem | None = None,
    ) -> list[MenuItem]:
        available = db.query(MenuItem).filter(MenuItem.available.is_(True)).all()
        requested_words = _words(requested_name or "")
        requested_words |= _cuisine_hint_words(requested_name or "")
        if item:
            requested_words |= _words(item.name)
            requested_words |= _words(item.description)
        scored: list[tuple[int, float, MenuItem]] = []
        for candidate in available:
            if item and candidate.id == item.id:
                continue
            candidate_words = _words(candidate.name) | _words(candidate.description)
            score = len(requested_words & candidate_words)
            if item and candidate.category == item.category:
                score += 5
            if item and candidate.vegetarian == item.vegetarian:
                score += 1
            if item and candidate.spicy == item.spicy:
                score += 1
            fallback_score = 1 if not requested_words else 0
            scored.append((score or fallback_score, -candidate.price, candidate))
        scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
        positive = [row for row in scored if row[0] > 0]
        candidates = positive or scored
        return [candidate for _, _, candidate in candidates[:3]]

    def _format_alternatives(self, items: list[MenuItem]) -> str:
        return "\n".join(f"- {item.name}: ${item.price:.2f}" for item in items)

    def _format_order_history(self, orders: list[Order]) -> str:
        blocks = ["Order History"]
        for order in orders:
            blocks.append(self._format_order_block(order))
        return "\n\n".join(blocks)

    def _format_reorder_candidate(self, order: Order) -> str:
        return (
            "I found your most recent matching order:\n\n"
            f"{self._format_order_items(order)}\n\n"
            "Would you like me to place the same order again?"
        )

    def _format_order_block(self, order: Order) -> str:
        created = order.created_at.strftime("%d %B %Y") if order.created_at else "Unknown"
        return (
            f"Order #{order.id}\n"
            f"Date: {created}\n"
            "Items:\n"
            f"{self._format_order_items(order)}\n"
            f"Status: {order.status.title()}\n"
            f"Total: ${self._order_total(order):.2f}"
        )

    def _format_order_items(self, order: Order) -> str:
        return "\n".join(f"- {item.quantity} x {item.item_name}" for item in order.items)

    def _order_total(self, order: Order) -> float:
        subtotal = sum(item.price * item.quantity for item in order.items)
        delivery = DELIVERY_FEE if order.delivery_method == "delivery" else 0.0
        return subtotal + (subtotal * TAX_RATE) + delivery

    def _identity_updates(self, kwargs: dict) -> dict[str, Any]:
        return {
            key: kwargs[key]
            for key in ["customer_id", "customer_name", "email", "phone"]
            if kwargs.get(key)
        }
