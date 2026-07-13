import re
from typing import Any

from app.agent.memory import ConversationMemory, empty_order_state
from app.database import SessionLocal
from app.models.menu import MenuItem


class OrderWorkflow:
    ready_words = {
        "done",
        "that's all",
        "thats all",
        "checkout",
        "place order",
        "submit order",
        "finish order",
        "review order",
    }
    confirm_words = {"yes", "confirm", "confirmed", "looks good", "place it", "submit it", "go ahead"}
    decline_words = {"no", "not yet", "change", "edit", "wait"}
    payment_words = {"pay", "payment", "card", "cash", "mobile", "mobile money", "gift card", "mpesa", "m-pesa"}
    payment_sent_words = {"paid", "sent", "done", "completed", "payment sent"}
    order_history_words = {"previous order", "previous orders", "order history", "last order", "ordered last"}
    reorder_words = {"same thing as last time", "same as last time", "reorder", "order the same"}
    new_order_words = {
        "new order",
        "new food",
        "order new food",
        "order something new",
        "start another order",
        "start a new order",
        "make a new order",
    }
    tax_rate = 0.0825
    delivery_fee = 4.99

    def __init__(self, agent: Any) -> None:
        self.agent = agent

    async def handle(self, message: str, memory: ConversationMemory) -> str | None:
        text = message.lower().strip()

        if self._is_reorder_request(text) or memory.order_status == "awaiting_reorder_confirmation":
            return await self._handle_reorder(message, text, memory)

        if self._is_order_history_request(text):
            return await self._handle_order_history(text, memory)

        if self._is_new_order_request(text):
            memory.order_id = None
            memory.reset_order_state()
            memory.order_status = "collecting"
            return "Absolutely. I'll start a new order for you. What would you like to order?"

        if self._is_cancel(text) and self._has_order_to_cancel(memory):
            if memory.order_id:
                return await self._cancel_submitted_order(memory)
            memory.reset_order_state()
            return "No problem. I cleared the current order. What would you like instead?"

        if self._should_handle_payment(text, memory):
            return await self._handle_payment(text, memory)

        lookup = self._lookup_menu_request(text, memory)
        if self._is_menu_request(text):
            if not lookup.get("item") and not lookup.get("requested_name"):
                return None
            if lookup.get("requested_name") and not lookup.get("item"):
                return None
            is_menu_browse = any(w in text for w in ["what", "show", "list", "have", "any", "all", "tell me"])
            if is_menu_browse and not self._has_quantity(text):
                return None
        if not self._should_handle_order(text, memory, lookup):
            return None
        return await self._handle_order(message, text, memory, lookup)

    async def _handle_order(
        self,
        message: str,
        text: str,
        memory: ConversationMemory,
        lookup: dict[str, Any],
    ) -> str:
        self._ensure_order_state(memory)

        if memory.order_status == "awaiting_confirmation":
            if self._is_confirmation(text):
                return await self._submit_order(memory)
            if self._is_decline(text):
                memory.order_status = "collecting"
                return "Of course. What would you like to change?"

        if memory.order_status == "awaiting_quantity":
            pending_item = self._pending_item(memory)
            if not pending_item:
                memory.order_status = "collecting"
                return "What would you like to order?"
            quantity = self._quantity(text)
            item = self._item_by_id(int(pending_item["menu_item_id"]))
            memory.order_state["pending_item"] = None
            if not item:
                memory.order_status = "collecting"
                return "I could not find that menu item anymore. What would you like instead?"
            if not item.available:
                memory.order_status = "collecting"
                return self._sold_out_response(item)
            self._add_item(memory, item, quantity)
            return self._next_order_prompt(memory, f"I've added {quantity} x {item.name}.")

        if memory.order_status == "awaiting_delivery_method":
            delivery_method = self._delivery_method(text)
            if not delivery_method:
                return "Would you like pickup or delivery?"
            memory.order_state["delivery_method"] = delivery_method
            return self._next_order_prompt(memory)

        if memory.order_status == "awaiting_address":
            memory.order_state["address"] = message.strip()
            return self._next_order_prompt(memory)

        if memory.order_status == "awaiting_payment_method":
            payment_method = self._payment_method(text)
            if not payment_method:
                return self._payment_method_prompt()
            memory.order_state["payment_method"] = payment_method
            memory.payment_method = payment_method
            return self._next_order_prompt(memory)

        if memory.order_status == "awaiting_customer_name" and not memory.customer_name:
            memory.customer_name = self._name_from_reply(message)
            return self._next_order_prompt(memory)

        if self._is_remove(text):
            return self._remove_item(text, memory)

        item = lookup.get("item")
        if memory.order_status == "paid" and (item or lookup.get("requested_name")):
            memory.order_id = None
            memory.reset_order_state()
            self._ensure_order_state(memory)

        if item:
            if not item.available:
                return self._sold_out_response(item)
            if not self._has_quantity(text):
                memory.order_state["pending_item"] = self._menu_line(item)
                memory.order_status = "awaiting_quantity"
                return f"Great choice! {item.name} is available. How many would you like?"
            quantity = self._quantity(text)
            self._add_item(memory, item, quantity)
            return self._next_order_prompt(memory, f"I've added {quantity} x {item.name}.")

        requested_name = lookup.get("requested_name")
        if requested_name:
            memory.order_status = "collecting"
            return self._not_found_response(requested_name)

        if self._is_ready_to_order(text):
            return self._next_order_prompt(memory)

        if memory.current_order_items():
            return self._next_order_prompt(memory)

        memory.order_status = "collecting"
        return "Of course. What would you like to order?"

    async def _handle_order_history(self, text: str, memory: ConversationMemory) -> str:
        args = self._identity_args(memory)
        if search := self._history_search(text):
            args["search"] = search
        result = await self.agent._execute_tool(
            "manage_order",
            {"action": "history", **args},
            memory,
        )
        return result.message

    async def _handle_reorder(
        self,
        message: str,
        text: str,
        memory: ConversationMemory,
    ) -> str:
        self._ensure_order_state(memory)
        if memory.order_status == "awaiting_reorder_confirmation":
            if self._is_decline(text):
                memory.order_state["pending_reorder"] = None
                memory.order_status = "collecting"
                return "No problem. What would you like to order instead?"
            if not self._is_confirmation(text):
                return "Would you like me to place the same order again?"

            order = memory.order_state.get("pending_reorder")
            if not isinstance(order, dict):
                memory.order_status = "collecting"
                return "I lost track of that previous order. Please ask me to show it again."
            unavailable = self._unavailable_reorder_items(order)
            if unavailable:
                memory.order_state["pending_reorder"] = None
                memory.order_status = "collecting"
                return unavailable
            memory.order_state = {
                **empty_order_state(),
                "items": [
                    {
                        "menu_item_id": item["menu_item_id"],
                        "name": item["item_name"],
                        "quantity": item["quantity"],
                        "price": item["price"],
                    }
                    for item in order.get("items", [])
                ],
                "delivery_method": order.get("delivery_method"),
                "address": order.get("delivery_address"),
                "payment_method": order.get("payment_method"),
            }
            memory.payment_method = memory.order_state.get("payment_method")
            return self._next_order_prompt(memory, "Perfect. I rebuilt that order.")

        args = self._identity_args(memory)
        if search := self._history_search(text):
            args["search"] = search
        result = await self.agent._execute_tool(
            "manage_order",
            {"action": "last_completed", **args},
            memory,
        )
        order = result.data.get("order")
        if result.success and order:
            memory.order_state["pending_reorder"] = order
            memory.order_status = "awaiting_reorder_confirmation"
        return result.message

    async def _submit_order(self, memory: ConversationMemory) -> str:
        if not memory.current_order_items():
            memory.order_status = "collecting"
            return "I do not have any items in the order yet. What would you like?"

        self._ensure_order_state(memory)
        customer_name = memory.customer_name or ("Guest" if memory.customer_id else None)
        if not customer_name:
            memory.order_status = "awaiting_customer_name"
            return "What name should I put on the order?"

        result = await self.agent._execute_tool(
            "manage_order",
            {
                "action": "create",
                "customer_id": memory.customer_id,
                "customer_name": customer_name,
                "email": memory.email,
                "phone": memory.phone,
                "items": memory.current_order_items(),
                "delivery_method": memory.order_state.get("delivery_method"),
                "delivery_address": memory.order_state.get("address"),
                "payment_method": memory.order_state.get("payment_method"),
            },
            memory,
        )
        if not result.success:
            memory.order_status = "collecting"
            return result.message

        memory.order_status = "awaiting_payment"
        memory.payment_status = "pending"
        method = memory.order_state.get("payment_method")
        if method == "mobile_money":
            payment = await self.agent._execute_tool(
                "process_payment",
                {"order_id": memory.order_id, "payment_method": method},
                memory,
            )
            return f"{result.message} {payment.message}"
        if method:
            payment = await self.agent._execute_tool(
                "process_payment",
                {"order_id": memory.order_id, "payment_method": method, "payment_confirmed": True},
                memory,
            )
            return f"{result.message} {payment.message}"
        return result.message

    async def _handle_payment(self, text: str, memory: ConversationMemory) -> str:
        if not memory.order_id:
            if memory.current_order_items():
                memory.order_status = "awaiting_confirmation"
                return self._confirmation_prompt(memory)
            return self._payment_method_prompt()

        method = self._payment_method(text)
        payment_confirmed = False
        if not method and memory.payment_method == "mobile_money" and self._payment_sent(text):
            method = "mobile_money"
            payment_confirmed = True
        if not method:
            memory.order_status = "awaiting_payment"
            memory.payment_status = memory.payment_status or "pending"
            return self._payment_method_prompt()

        result = await self.agent._execute_tool(
            "process_payment",
            {
                "order_id": memory.order_id,
                "payment_method": method,
                "payment_confirmed": payment_confirmed,
                "simulate_failure": self._wants_failure(text),
            },
            memory,
        )
        if result.success:
            return f"{result.message} Thank you. Your order is confirmed and paid."
        return result.message

    async def _cancel_submitted_order(self, memory: ConversationMemory) -> str:
        result = await self.agent._execute_tool(
            "manage_order",
            {"action": "cancel", "order_id": memory.order_id},
            memory,
        )
        if result.success:
            memory.reset_order_state()
        return result.message

    def _next_order_prompt(self, memory: ConversationMemory, prefix: str | None = None) -> str:
        self._ensure_order_state(memory)
        if not memory.current_order_items():
            memory.order_status = "collecting"
            prompt = "What would you like to order?"
        elif not memory.order_state.get("delivery_method"):
            memory.order_status = "awaiting_delivery_method"
            prompt = "Would you like pickup or delivery?"
        elif memory.order_state.get("delivery_method") == "delivery" and not memory.order_state.get("address"):
            memory.order_status = "awaiting_address"
            prompt = "What delivery address should I use?"
        elif not memory.order_state.get("payment_method"):
            memory.order_status = "awaiting_payment_method"
            prompt = self._payment_method_prompt()
        elif not memory.customer_name and not memory.customer_id:
            memory.order_status = "awaiting_customer_name"
            prompt = "What name should I put on the order?"
        else:
            memory.order_status = "awaiting_confirmation"
            prompt = self._confirmation_prompt(memory)
        return f"{prefix}\n\n{prompt}" if prefix else prompt

    def _add_item(self, memory: ConversationMemory, item: MenuItem, quantity: int) -> None:
        self._ensure_order_state(memory)
        items = memory.order_state.setdefault("items", [])
        existing = next((line for line in items if line.get("menu_item_id") == item.id), None)
        if existing:
            existing["quantity"] = int(existing.get("quantity", 0)) + quantity
        else:
            items.append({**self._menu_line(item), "quantity": quantity})
        memory.order_state["status"] = "collecting_information"

    def _remove_item(self, text: str, memory: ConversationMemory) -> str:
        items = memory.current_order_items()
        if not items:
            memory.order_status = "collecting"
            return "There is nothing in the current order yet. What would you like to add?"
        match = next((item for item in items if item["name"].lower() in text), None)
        if not match:
            return "Which item should I remove from the order?"
        items.remove(match)
        memory.order_state["items"] = items
        if not items:
            memory.order_status = "collecting"
            return f"I removed {match['name']}. What would you like instead?"
        return self._next_order_prompt(memory, f"I removed {match['name']}.")

    def _confirmation_prompt(self, memory: ConversationMemory) -> str:
        return f"{self._order_summary(memory)}\n\nWould you like me to place this order?"

    def _order_summary(self, memory: ConversationMemory) -> str:
        subtotal = 0.0
        lines = ["Order Summary", "", "Items"]
        for item in memory.current_order_items():
            line_total = float(item["price"]) * int(item["quantity"])
            subtotal += line_total
            lines.append(f"- {item['quantity']} x {item['name']}: ${line_total:.2f}")
        delivery_method = memory.order_state.get("delivery_method") or "Not selected"
        delivery_fee = self.delivery_fee if delivery_method == "delivery" else 0.0
        tax = subtotal * self.tax_rate
        total = subtotal + tax + delivery_fee
        payment_method = memory.order_state.get("payment_method") or "Not selected"
        lines.extend(
            [
                "",
                f"Subtotal: ${subtotal:.2f}",
                f"Tax: ${tax:.2f}",
                f"Delivery Fee: ${delivery_fee:.2f}",
                f"Total: ${total:.2f}",
                f"Delivery Method: {self._display(delivery_method)}",
            ]
        )
        if delivery_method == "delivery" and memory.order_state.get("address"):
            lines.append(f"Delivery Address: {memory.order_state['address']}")
        lines.append(f"Payment Method: {self._display(payment_method)}")
        return "\n".join(lines)

    def _lookup_menu_request(self, text: str, memory: ConversationMemory) -> dict[str, Any]:
        requested_name = self._requested_item_name(text)
        db = SessionLocal()
        try:
            items = db.query(MenuItem).all()
            item = self._match_menu_item(items, text)
            if not item and requested_name:
                item = self._match_menu_item(items, requested_name.lower())
            if not item and not requested_name and self._looks_like_bare_item_request(text, memory):
                requested_name = self._display_requested_name(text)
                item = self._match_menu_item(items, text)
            return {"item": item, "requested_name": requested_name}
        finally:
            db.close()

    def _match_menu_item(self, items: list[MenuItem], text: str) -> MenuItem | None:
        exact = next((item for item in items if item.name.lower() in text), None)
        if exact:
            return exact
        text_words = self._words(text)
        scored = []
        for item in items:
            name_words = self._words(item.name)
            score = len(text_words & name_words)
            if score:
                scored.append((score, len(name_words), item))
        if not scored:
            return None
        scored.sort(key=lambda row: (row[0], -row[1]), reverse=True)
        best_score, _, best_item = scored[0]
        return best_item if best_score >= 2 or (best_score == 1 and len(scored) == 1) else None

    def _not_found_response(self, requested_name: str) -> str:
        alternatives = self._alternatives(requested_name=requested_name)
        if not alternatives:
            return f"We don't currently have {requested_name} on our menu. Would you like to see the menu?"
        return (
            f"We don't currently have {requested_name} on our menu.\n\n"
            "Here are some similar dishes you might enjoy:\n\n"
            f"{self._format_alternatives(alternatives)}\n\n"
            "Would you like one of these instead?"
        )

    def _sold_out_response(self, item: MenuItem) -> str:
        alternatives = self._alternatives(item=item)
        if not alternatives:
            return f"I'm sorry, {item.name} is currently sold out. Would you like to see the menu?"
        return (
            f"I'm sorry, {item.name} is currently sold out.\n\n"
            "Here are some similar dishes that are available:\n\n"
            f"{self._format_alternatives(alternatives)}\n\n"
            "Would you like one of these instead?"
        )

    def _alternatives(
        self,
        requested_name: str | None = None,
        item: MenuItem | None = None,
    ) -> list[MenuItem]:
        db = SessionLocal()
        try:
            available = db.query(MenuItem).filter(MenuItem.available.is_(True)).all()
            requested_words = self._words(requested_name or "")
            requested_words |= self._cuisine_hint_words(requested_name or "")
            if item:
                requested_words |= self._words(item.name)
                requested_words |= self._words(item.description)
            scored: list[tuple[int, float, MenuItem]] = []
            for candidate in available:
                if item and candidate.id == item.id:
                    continue
                candidate_words = self._words(candidate.name) | self._words(candidate.description)
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
        finally:
            db.close()

    def _unavailable_reorder_items(self, order: dict) -> str | None:
        db = SessionLocal()
        try:
            for line in order.get("items", []):
                item = db.query(MenuItem).filter(MenuItem.id == int(line["menu_item_id"])).first()
                if not item:
                    return self._not_found_response(line.get("item_name", "that item"))
                if not item.available:
                    return self._sold_out_response(item)
        finally:
            db.close()
        return None

    def _item_by_id(self, menu_item_id: int) -> MenuItem | None:
        db = SessionLocal()
        try:
            return db.query(MenuItem).filter(MenuItem.id == menu_item_id).first()
        finally:
            db.close()

    def _identity_args(self, memory: ConversationMemory) -> dict[str, Any]:
        return {
            key: value
            for key, value in {
                "customer_id": memory.customer_id,
                "customer_name": memory.customer_name,
                "email": memory.email,
                "phone": memory.phone,
            }.items()
            if value
        }

    def _ensure_order_state(self, memory: ConversationMemory) -> None:
        if not isinstance(memory.order_state, dict):
            memory.order_state = empty_order_state()
        defaults = empty_order_state()
        for key, value in defaults.items():
            memory.order_state.setdefault(key, value)

    def _pending_item(self, memory: ConversationMemory) -> dict[str, Any] | None:
        item = memory.order_state.get("pending_item")
        return item if isinstance(item, dict) else None

    def _menu_line(self, item: MenuItem) -> dict[str, Any]:
        return {
            "menu_item_id": item.id,
            "name": item.name,
            "price": float(item.price),
        }

    def _format_alternatives(self, items: list[MenuItem]) -> str:
        return "\n".join(f"- {item.name}: ${item.price:.2f}" for item in items)

    def _payment_method_prompt(self) -> str:
        return "How would you like to pay? We accept card, cash, mobile money, or gift card."

    def _display(self, value: str) -> str:
        return value.replace("_", " ").title()

    def _should_handle_order(
        self,
        text: str,
        memory: ConversationMemory,
        lookup: dict[str, Any],
    ) -> bool:
        if memory.order_status in {
            "collecting",
            "awaiting_quantity",
            "awaiting_delivery_method",
            "awaiting_address",
            "awaiting_payment_method",
            "awaiting_customer_name",
            "awaiting_confirmation",
        }:
            return True
        if lookup.get("item") or lookup.get("requested_name"):
            return True
        return any(word in text for word in ["order", "add", "remove", "cart", "checkout"])

    def _should_handle_payment(self, text: str, memory: ConversationMemory) -> bool:
        if memory.order_status == "awaiting_payment":
            return True
        if memory.payment_status in {"pending", "failed"} and memory.order_id:
            return True
        return any(word in text for word in self.payment_words) and bool(memory.order_id)

    def _is_ready_to_order(self, text: str) -> bool:
        return any(word in text for word in self.ready_words)

    def _is_confirmation(self, text: str) -> bool:
        return any(word in text for word in self.confirm_words)

    def _is_decline(self, text: str) -> bool:
        return any(word in text for word in self.decline_words)

    def _is_cancel(self, text: str) -> bool:
        if "clear order" in text or "start over" in text:
            return True
        return bool(re.search(r"\bcancel\b", text))

    def _is_remove(self, text: str) -> bool:
        return "remove" in text or "delete" in text

    def _is_menu_request(self, text: str) -> bool:
        return any(word in text for word in ["menu", "recommend", "vegetarian", "vegan", "spicy"])

    def _is_order_history_request(self, text: str) -> bool:
        return any(word in text for word in self.order_history_words)

    def _is_reorder_request(self, text: str) -> bool:
        return any(word in text for word in self.reorder_words)

    def _is_new_order_request(self, text: str) -> bool:
        return any(word in text for word in self.new_order_words)

    def _has_order_to_cancel(self, memory: ConversationMemory) -> bool:
        return bool(memory.current_order_items() or memory.order_id) and memory.order_status != "paid"

    def _has_quantity(self, text: str) -> bool:
        if re.search(r"\b\d+\b", text):
            return True
        return any(re.search(rf"\b{word}\b", text) for word in self._number_words())

    def _quantity(self, text: str) -> int:
        if match := re.search(r"\b(\d+)\b", text):
            return max(1, int(match.group(1)))
        for word, value in self._number_words().items():
            if re.search(rf"\b{word}\b", text):
                return value
        return 1

    def _number_words(self) -> dict[str, int]:
        return {
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
            "six": 6,
            "seven": 7,
            "eight": 8,
            "nine": 9,
            "ten": 10,
        }

    def _delivery_method(self, text: str) -> str | None:
        if "pickup" in text or "pick up" in text or "collect" in text:
            return "pickup"
        if "delivery" in text or "deliver" in text:
            return "delivery"
        return None

    def _payment_method(self, text: str) -> str | None:
        if "mobile" in text or "mobile money" in text or "mpesa" in text or "m-pesa" in text:
            return "mobile_money"
        if "gift" in text:
            return "gift_card"
        if "card" in text or "credit" in text or "debit" in text:
            return "card"
        if "cash" in text:
            return "cash"
        return None

    def _wants_failure(self, text: str) -> bool:
        return any(word in text for word in ["fail", "failed", "decline", "declined"])

    def _payment_sent(self, text: str) -> bool:
        return any(word in text for word in self.payment_sent_words)

    def _history_search(self, text: str) -> str | None:
        categories = ["pizza", "pasta", "salmon", "fish", "chicken", "dessert", "drink"]
        return next((word for word in categories if word in text), None)

    def _requested_item_name(self, text: str) -> str | None:
        reservation_words = {"reserve", "reservation", "book", "booking", "table", "seat", "seating"}
        order_keywords = {"order", "add", "get me", "can i get", "i'd like", "id like", "i want"}
        has_order_keyword = any(kw in text.lower() for kw in order_keywords)
        has_reservation_context = any(w in text.lower() for w in reservation_words)

        if has_reservation_context and not has_order_keyword:
            return None

        patterns = [
            r"(?:i want|i'd like|id like|order|add|get me|can i get)\s+(?:\d+\s+|one\s+|two\s+|three\s+)?(.+)",
            r"do you have\s+(.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if not match:
                continue
            value = match.group(1)
            value = re.split(r"\b(?:for|with|and|please|to go|pickup|delivery)\b", value, maxsplit=1)[0]
            value = re.sub(r"[^a-z0-9 '&-]", "", value, flags=re.I).strip()
            if value and value not in {"food", "new food", "something", "something new", "a table", "a table for"}:
                if any(w in value.lower() for w in reservation_words):
                    continue
                return " ".join(part.capitalize() for part in value.split())
        return None

    def _looks_like_bare_item_request(self, text: str, memory: ConversationMemory) -> bool:
        if memory.order_status not in {"collecting", "awaiting_quantity"} and not (
            memory.order_status is None and self._cuisine_hint_words(text)
        ):
            return False
        if self._delivery_method(text) or self._payment_method(text):
            return False
        blocked_words = {
            "menu",
            "recommend",
            "reservation",
            "reserve",
            "booking",
            "table",
            "book",
            "hours",
            "address",
            "parking",
            "wifi",
            "wi-fi",
            "delivery",
            "pickup",
            "cancel",
            "history",
            "previous",
        }
        words = self._words(text)
        if not words or words & blocked_words:
            return False
        return 1 <= len(words) <= 4

    def _display_requested_name(self, text: str) -> str:
        clean = re.sub(r"[^a-z0-9 '&-]", "", text, flags=re.I).strip()
        return " ".join(part.capitalize() for part in clean.split())

    def _name_from_reply(self, message: str) -> str:
        text = message.strip()
        text = re.sub(r"^(my name is|name is|it is|it's|for)\s+", "", text, flags=re.I)
        return " ".join(part.capitalize() for part in text.split())[:100] or "Guest"

    def _words(self, text: str) -> set[str]:
        stop_words = {
            "i",
            "want",
            "order",
            "add",
            "the",
            "a",
            "an",
            "please",
            "my",
            "last",
            "same",
            "thing",
            "time",
        }
        return {
            word
            for word in re.findall(r"[a-z0-9]+", text.lower())
            if word not in stop_words and len(word) > 1
        }

    def _cuisine_hint_words(self, text: str) -> set[str]:
        lowered = text.lower()
        hints: set[str] = set()
        if any(word in lowered for word in ["sushi", "seafood", "fish"]):
            hints.update({"fish", "salmon", "seafood", "calamari", "shrimp", "squid"})
        if "pizza" in lowered:
            hints.update({"pizza", "tomato", "mozzarella", "cheese"})
        if "pasta" in lowered or "lasagna" in lowered:
            hints.update({"pasta", "spaghetti", "penne", "carbonara", "tomato", "parmesan"})
        if "burger" in lowered:
            hints.update({"chicken", "bread", "cheese"})
        return hints
