from django.db import transaction

from agent.tools.base import BaseTool, ToolResult, TAX_RATE, DELIVERY_FEE
from agent.utils import words as _words, cuisine_hint_words as _cuisine_hint_words
from menu.models import MenuItem
from orders.models import Order, OrderItem


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

    def execute(self, **kwargs):
        action = kwargs["action"]
        if action == "history":
            return self._order_history(kwargs)
        if action == "last_completed":
            return self._last_completed_order(kwargs)
        if action == "create" and kwargs.get("items"):
            idempotency_key = kwargs.get("idempotency_key")
            if idempotency_key:
                existing = Order.objects.filter(idempotency_key=idempotency_key).first()
                if existing:
                    return ToolResult(
                        success=True,
                        message=f"Order already exists. ID: {existing.id}.",
                        data={"order": existing.to_dict()},
                        memory_updates={"order_id": existing.id, "customer_name": existing.customer_name},
                    )
            if not kwargs.get("confirmed"):
                return self._require_confirmation(kwargs)
            return self._create_order(kwargs, idempotency_key)
        order = self._find_or_create_order(kwargs)
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

    def _require_confirmation(self, kwargs):
        items = kwargs.get("items", [])
        lines = [f"{item.get('quantity', 1)} x {item.get('name', 'Unknown')}" for item in items]
        summary = "Order Summary:\n" + "\n".join(lines) if lines else "No items in this order yet."
        total_line = ""
        if items:
            subtotal = sum(float(item.get("price", 0)) * int(item.get("quantity", 1)) for item in items)
            delivery = DELIVERY_FEE if kwargs.get("delivery_method") == "delivery" else 0.0
            total = subtotal + (subtotal * TAX_RATE) + delivery
            total_line = f"\nTotal: ${total:.2f}"
        delivery_info = f"\nDelivery method: {kwargs.get('delivery_method', 'Not specified')}"
        if kwargs.get("delivery_method") == "delivery" and kwargs.get("delivery_address"):
            delivery_info += f"\nDelivery address: {kwargs['delivery_address']}"
        return ToolResult(
            success=False,
            message=f"{summary}{total_line}{delivery_info}\n\nPlease confirm by calling this tool again with confirmed=True to place the order.",
            next_action="awaiting_confirmation",
            data={
                "confirmation_required": True,
                "summary": f"{summary}{total_line}{delivery_info}",
            },
        )

    def _create_order(self, kwargs, idempotency_key=None):
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

        order_items = []
        for requested in kwargs["items"]:
            item = self._menu_item_by_id_or_name(
                requested.get("menu_item_id"),
                requested.get("name", ""),
            )
            if not item:
                return self._item_not_found(requested.get("name", "that item"))
            if not item.available:
                return self._item_unavailable(item)
            order_items.append(
                {
                    "menu_item_id": item.id,
                    "name": item.name,
                    "quantity": int(requested.get("quantity") or 1),
                    "price": float(item.price),
                }
            )

        with transaction.atomic():
            order = Order(
                customer_name=kwargs["customer_name"],
                customer_id=kwargs.get("customer_id"),
                email=kwargs.get("email"),
                phone=kwargs.get("phone"),
                delivery_method=kwargs.get("delivery_method"),
                delivery_address=kwargs.get("delivery_address"),
                payment_method=kwargs.get("payment_method"),
                status="submitted",
                idempotency_key=idempotency_key,
            )
            order.save()
            for item in order_items:
                OrderItem.objects.create(
                    order=order,
                    menu_item_id=item["menu_item_id"],
                    item_name=item["name"],
                    quantity=int(item["quantity"]),
                    price=float(item["price"]),
                )

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

    def _find_or_create_order(self, kwargs):
        if order_id := kwargs.get("order_id"):
            order = Order.objects.filter(id=order_id).first()
            if order:
                return order
        name = kwargs.get("customer_name") or "Guest"
        query = Order.objects.filter(status="active")
        if kwargs.get("customer_id"):
            query = query.filter(customer_id=kwargs["customer_id"])
        elif kwargs.get("email"):
            query = query.filter(email=kwargs["email"])
        elif kwargs.get("phone"):
            query = query.filter(phone=kwargs["phone"])
        else:
            query = query.filter(customer_name=name)
        order = query.first()
        if order:
            return order
        order = Order(
            customer_name=name,
            customer_id=kwargs.get("customer_id"),
            email=kwargs.get("email"),
            phone=kwargs.get("phone"),
        )
        order.save()
        return order

    def _add_item(self, order, kwargs):
        item = self._match_menu_item(kwargs.get("item_name", ""))
        if not item:
            return self._item_not_found(kwargs.get("item_name", "that item"))
        if not item.available:
            return self._item_unavailable(item)
        quantity = int(kwargs.get("quantity") or 1)
        items_list = list(order.items.all())
        existing = next((line for line in items_list if line.menu_item_id == item.id), None)
        if existing:
            existing.quantity += quantity
            existing.save()
        else:
            OrderItem.objects.create(
                order=order,
                menu_item_id=item.id,
                item_name=item.name,
                quantity=quantity,
                price=item.price,
            )
        order.refresh_from_db()
        return ToolResult(
            success=True,
            message=f"Added {quantity} x {item.name} to order ID: {order.id}.",
            data={"order": order.to_dict(), "added_item": item.name, "quantity": quantity},
            memory_updates={"order_id": order.id, "customer_name": order.customer_name},
        )

    def _remove_item(self, order, kwargs):
        query = kwargs.get("item_name", "").lower()
        items_list = list(order.items.all())
        item = next((line for line in items_list if line.item_name.lower() in query), None)
        if not item:
            return ToolResult(
                success=False,
                message="I could not find that item in the current order.",
                missing_fields=["item_name"],
                memory_updates={"order_id": order.id, "customer_name": order.customer_name},
                next_action="ask_user",
            )
        item_name = item.item_name
        item.delete()
        order.refresh_from_db()
        return ToolResult(
            success=True,
            message=f"Removed {item_name} from order ID: {order.id}.",
            data={"order": order.to_dict(), "removed_item": item_name},
            memory_updates={"order_id": order.id, "customer_name": order.customer_name},
        )

    def _cancel_order(self, order):
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
        order.save()
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
        lines.append(f"Subtotal: ${sum(item.quantity * item.price for item in items_list):.2f}")
        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={"order": order.to_dict()},
            memory_updates={"order_id": order.id, "customer_name": order.customer_name},
        )

    def _match_menu_item(self, query):
        items = list(MenuItem.objects.all())
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

    def _menu_item_by_id_or_name(self, menu_item_id, name):
        if menu_item_id:
            item = MenuItem.objects.filter(id=int(menu_item_id)).first()
            if item:
                return item
        return self._match_menu_item(name)

    def _order_history(self, kwargs):
        orders_result = self._customer_orders(kwargs, newest_first=False)
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

    def _last_completed_order(self, kwargs):
        orders_result = self._customer_orders(kwargs, newest_first=True)
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

    def _customer_orders(self, kwargs, newest_first):
        query = Order.objects.all()
        if kwargs.get("customer_id"):
            query = query.filter(customer_id=kwargs["customer_id"])
        elif kwargs.get("email"):
            query = query.filter(email=kwargs["email"])
        elif kwargs.get("phone"):
            query = query.filter(phone=kwargs["phone"])
        elif kwargs.get("order_id"):
            query = query.filter(id=int(kwargs["order_id"]))
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
        sort_prefix = "-" if newest_first else ""
        return list(query.order_by(f"{sort_prefix}created_at", f"{sort_prefix}id"))

    def _filter_orders(self, orders, search):
        if not search:
            return orders
        search_words = _words(search)
        if not search_words:
            return orders
        return [
            order
            for order in orders
            if any(search_words & _words(item.item_name) for item in order.items.all())
        ]

    def _item_not_found(self, requested_name):
        alternatives = self._alternatives(requested_name=requested_name)
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

    def _item_unavailable(self, item):
        alternatives = self._alternatives(item=item)
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

    def _alternatives(self, requested_name=None, item=None):
        available = list(MenuItem.objects.filter(available=True))
        requested_words = _words(requested_name or "")
        requested_words |= _cuisine_hint_words(requested_name or "")
        if item:
            requested_words |= _words(item.name)
            requested_words |= _words(item.description)
        scored = []
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
            f"Total: ${self._order_total(order):.2f}"
        )

    def _format_order_items(self, order):
        return "\n".join(f"- {item.quantity} x {item.item_name}" for item in order.items.all())

    def _order_total(self, order):
        subtotal = sum(item.price * item.quantity for item in order.items.all())
        delivery = DELIVERY_FEE if order.delivery_method == "delivery" else 0.0
        return subtotal + (subtotal * TAX_RATE) + delivery

    def _identity_updates(self, kwargs):
        return {
            key: kwargs[key]
            for key in ["customer_id", "customer_name", "email", "phone"]
            if kwargs.get(key)
        }
