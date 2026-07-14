import re
from typing import Any

from agent.memory import ConversationMemory
from agent.utils import (
    parse_date,
    parse_time,
    parse_party_size,
    extract_email,
    extract_phone,
    extract_name,
    looks_like_phone,
)


class LocalPlanner:
    def plan(self, message: str, memory: ConversationMemory) -> list[dict[str, Any]]:
        text = message.lower()
        has_explicit_keyword = self._has_explicit_intent_keyword(text)

        if "reservation" in text or "table" in text or "book" in text or "reserve" in text:
            return [{"tool": "manage_reservation", "args": self._reservation_args(text, memory)}]

        if any(word in text for word in ["order", "add", "remove", "cart"]):
            return [{"tool": "manage_order", "args": self._order_args(message, memory)}]

        if "menu" in text or "recommend" in text or "vegetarian" in text or "vegan" in text or "spicy" in text:
            return [{"tool": "list_menu_items", "args": self._menu_args(text)}]

        if "bill" in text or "total" in text or "split" in text:
            return [{"tool": "calculate_bill", "args": self._billing_args(text, memory)}]

        if self._is_faq(text):
            return [{"tool": "answer_faq", "args": {"question": message}}]

        if not has_explicit_keyword:
            if self._provides_reservation_followup(text, memory):
                return [{"tool": "manage_reservation", "args": self._reservation_args(text, memory)}]

            if self._refers_to_existing_reservation(text, memory):
                return [{"tool": "manage_reservation", "args": self._reservation_args(text, memory)}]

            if memory.current_order_items() and self._provides_order_followup(text, memory):
                return [{"tool": "manage_order", "args": self._order_args(message, memory)}]

        if self._has_reservation_context(memory):
            return [{"tool": "manage_reservation", "args": self._reservation_args(text, memory)}]

        if memory.current_order_items():
            return [{"tool": "manage_order", "args": self._order_args(message, memory)}]

        return [{"tool": "answer_faq", "args": {"question": message}}]

    def _has_explicit_intent_keyword(self, text: str) -> bool:
        return any(
            word in text
            for word in [
                "reservation", "table", "book", "reserve",
                "order", "add", "remove", "cart",
                "menu", "recommend", "vegetarian", "vegan", "spicy",
                "bill", "total", "split",
                "hour", "hours", "open", "address", "parking", "wifi",
            ]
        )

    def _has_reservation_context(self, memory: ConversationMemory) -> bool:
        return bool(
            memory.party_size
            or memory.reservation_date
            or memory.reservation_time
            or memory.reservation_id
        )

    def _provides_reservation_followup(self, text: str, memory: ConversationMemory) -> bool:
        if not self._has_reservation_context(memory):
            return False
        if memory.reservation_id:
            return False
        has_contact = "@" in text or looks_like_phone(text) or "my name is" in text
        has_time = bool(parse_time(text))
        has_date = bool(parse_date(text))
        return has_contact or has_time or has_date

    def _provides_order_followup(self, text: str, memory: ConversationMemory) -> bool:
        if not memory.current_order_items():
            return False
        has_delivery = any(word in text for word in ["pickup", "delivery", "collect"])
        has_payment = any(
            word in text
            for word in ["card", "cash", "mobile", "gift", "mpesa"]
        )
        return has_delivery or has_payment

    def _refers_to_existing_reservation(self, text: str, memory: ConversationMemory) -> bool:
        action = any(word in text for word in ["change", "update", "modify", "cancel"])
        return bool(memory.reservation_id and action)

    def _is_faq(self, text: str) -> bool:
        if re.search(r"\d+\s*hours?", text):
            has_time_word = False
        else:
            has_time_word = "hour" in text

        return any(
            word in text
            for word in ["open", "address", "parking", "wifi", "wi-fi", "pay", "delivery"]
        ) or (has_time_word)

    def _menu_args(self, text: str) -> dict[str, Any]:
        args: dict[str, Any] = {}
        if "vegetarian" in text:
            args["vegetarian"] = True
        if "vegan" in text:
            args["vegan"] = True
        if "spicy" in text:
            args["spicy"] = True
        if match := re.search(r"(?:under|below|less than)\s*\$?(\d+)", text):
            args["max_price"] = float(match.group(1))
        return args

    def _reservation_args(self, text: str, memory: ConversationMemory) -> dict[str, Any]:
        action = "create"
        if "cancel" in text:
            action = "cancel"
        elif "change" in text or "update" in text or "modify" in text:
            action = "update"
        elif "available" in text or "availability" in text:
            action = "check"
        args: dict[str, Any] = {"action": action}
        if memory.reservation_id:
            args["reservation_id"] = memory.reservation_id
        if size := parse_party_size(text):
            args["party_size"] = size
        elif memory.party_size:
            args["party_size"] = memory.party_size
        if res_date := parse_date(text):
            args["reservation_date"] = res_date
        elif memory.reservation_date:
            args["reservation_date"] = memory.reservation_date
        if res_time := parse_time(text):
            args["reservation_time"] = res_time
        elif memory.reservation_time:
            args["reservation_time"] = memory.reservation_time

        if raw_email := extract_email(text):
            args["email"] = raw_email
        elif memory.email:
            args["email"] = memory.email

        if raw_phone := extract_phone(text):
            args["phone"] = raw_phone
        elif memory.phone:
            args["phone"] = memory.phone

        if raw_name := extract_name(text):
            args["customer_name"] = raw_name
        elif memory.customer_name:
            args["customer_name"] = memory.customer_name

        return args

    def _order_args(self, message: str, memory: ConversationMemory) -> dict[str, Any]:
        text = message.lower()
        action = "show"
        if re.search(r"\bcancel\b", text):
            action = "cancel"
        elif "remove" in text:
            action = "remove"
        elif "add" in text or "order" in text:
            action = "add"
        args: dict[str, Any] = {"action": action, "customer_name": memory.customer_name or "Guest"}
        if memory.order_id:
            args["order_id"] = memory.order_id
        if action in {"add", "remove"}:
            args["item_name"] = message
            args["quantity"] = self._quantity(text)
        return args

    def _billing_args(self, text: str, memory: ConversationMemory) -> dict[str, Any]:
        args: dict[str, Any] = {"customer_name": memory.customer_name or "Guest"}
        if memory.order_id:
            args["order_id"] = memory.order_id
        if match := re.search(r"split (?:by|between|among)?\s*(\d+)", text):
            args["split_count"] = int(match.group(1))
        return args

    def _quantity(self, text: str) -> int:
        match = re.search(r"\b(\d+)\b", text)
        return int(match.group(1)) if match else 1
