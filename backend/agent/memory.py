import re
from dataclasses import dataclass, field
from typing import Any

from agent.utils import (
    parse_date,
    parse_time,
    parse_party_size,
    extract_email,
    extract_phone,
)


@dataclass
class ToolResult:
    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)
    memory_updates: dict[str, Any] = field(default_factory=dict)
    next_action: str | None = None

    def to_text(self) -> str:
        return self.message


def empty_order_state() -> dict[str, Any]:
    return {
        "items": [],
        "delivery_method": None,
        "address": None,
        "payment_method": None,
        "status": "collecting_information",
        "pending_item": None,
        # Reserved for future multi-turn slot filling
        "pending_action": None,
        "waiting_for": None,
    }


@dataclass
class ConversationMemory:
    customer_id: str | None = None
    customer_name: str | None = None
    phone: str | None = None
    email: str | None = None
    reservation_id: int | None = None
    reservation_date: str | None = None
    reservation_time: str | None = None
    party_size: int | None = None
    order_id: int | None = None
    order_state: dict[str, Any] = field(default_factory=empty_order_state)
    order_status: str | None = None
    payment_method: str | None = None
    payment_status: str | None = None
    payment_id: str | None = None
    reservation_status: str | None = None
    notes: list[str] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    discussed_topics: list[str] = field(default_factory=list)
    conversation_summary: str | None = None

    @classmethod
    def from_history(cls, history: list[dict] | None) -> "ConversationMemory":
        memory = cls()
        for message in history or []:
            content = message.get("content", "")
            memory._learn_from_text(content)
        return memory

    @classmethod
    def from_state(cls, state: dict) -> "ConversationMemory":
        return cls(
            customer_name=state.get("customer_name"),
            customer_id=state.get("customer_id"),
            phone=state.get("phone"),
            email=state.get("email"),
            reservation_id=state.get("reservation_id"),
            reservation_date=state.get("reservation_date"),
            reservation_time=state.get("reservation_time"),
            party_size=state.get("party_size"),
            order_id=state.get("order_id"),
            order_state=state.get("order_state") or empty_order_state(),
            order_status=state.get("order_status"),
            payment_method=state.get("payment_method"),
            payment_status=state.get("payment_status"),
            payment_id=state.get("payment_id"),
            reservation_status=state.get("reservation_status"),
            discussed_topics=state.get("discussed_topics") or [],
            conversation_summary=state.get("conversation_summary"),
        )

    def remember_user_message(self, message: str) -> None:
        self._learn_from_text(message)

    def remember_message(self, message: str) -> None:
        self._learn_from_text(message)

    def remember_tool_result(self, result, tool_name: str | None = None) -> None:
        for key, value in result.memory_updates.items():
            if hasattr(self, key):
                setattr(self, key, value)
        if result.message:
            self._learn_from_text(result.message)
        self.tool_results.append({
            "success": result.success,
            "data": result.data,
            "memory_updates": result.memory_updates,
            "tool_name": tool_name or "",
        })

    def to_state(self) -> dict:
        return {
            "customer_name": self.customer_name,
            "customer_id": self.customer_id,
            "phone": self.phone,
            "email": self.email,
            "reservation_id": self.reservation_id,
            "reservation_date": self.reservation_date,
            "reservation_time": self.reservation_time,
            "party_size": self.party_size,
            "order_id": self.order_id,
            "order_state": self.order_state,
            "order_status": self.order_status,
            "payment_method": self.payment_method,
            "payment_status": self.payment_status,
            "payment_id": self.payment_id,
            "reservation_status": self.reservation_status,
            "discussed_topics": self.discussed_topics,
            "conversation_summary": self.conversation_summary,
        }

    def _learn_from_text(self, text: str) -> None:
        if match := re.search(r"\bmy name is ([A-Za-z]+(?: [A-Za-z]+)?)", text, re.I):
            self.customer_name = self._clean_name(match.group(1))
        if match := re.search(r"\bfor ([A-Za-z]+(?: [A-Za-z]+)?)", text, re.I):
            self.customer_name = self.customer_name or self._clean_name(match.group(1))
        if email := extract_email(text):
            self.email = email
        if phone := extract_phone(text):
            lower_text = text.lower()
            is_restaurant_payment_number = "company number" in lower_text or "mobile money" in lower_text
            if not is_restaurant_payment_number:
                self.phone = phone
        if match := re.search(r"\bReservation(?: confirmed!)? \(?ID:?\s*(\d+)\)?", text, re.I):
            self.reservation_id = int(match.group(1))
        if match := re.search(r"\bOrder(?: created)? \(?ID:?\s*(\d+)\)?", text, re.I):
            self.order_id = int(match.group(1))
        if party_size := parse_party_size(text):
            self.party_size = party_size
        if res_date := parse_date(text):
            self.reservation_date = res_date
        if res_time := parse_time(text):
            self.reservation_time = res_time

    def as_context(self) -> str:
        parts: list[str] = []
        if self.customer_name:
            parts.append(f"customer_name={self.customer_name}")
        if self.customer_id:
            parts.append(f"customer_id={self.customer_id}")
        if self.email:
            parts.append(f"email={self.email}")
        if self.phone:
            parts.append(f"phone={self.phone}")
        if self.reservation_id:
            parts.append(f"reservation_id={self.reservation_id}")
        if self.reservation_date and self.reservation_time:
            parts.append(f"reservation={self.reservation_date} {self.reservation_time}")
        if self.order_id:
            parts.append(f"order_id={self.order_id}")
        if self.order_status:
            parts.append(f"order_status={self.order_status}")
        if self.current_order_items():
            parts.append(f"pending_order={self.current_order_summary()}")
        if self.payment_status:
            parts.append(f"payment_status={self.payment_status}")
        return ", ".join(parts) if parts else "No known conversation memory yet."

    def has_reservation_details(self) -> bool:
        return bool(self.reservation_date and self.reservation_time and self.party_size)

    def current_order_items(self) -> list[dict[str, Any]]:
        items = self.order_state.get("items", [])
        return items if isinstance(items, list) else []

    def current_order_summary(self) -> str:
        parts = []
        for item in self.current_order_items():
            parts.append(f"{item.get('quantity', 1)} x {item.get('name')}")
        return ", ".join(parts)

    def has_pending_slot(self) -> str | None:
        """Return the slot name the system is waiting for, or None.

        Checks order_status first, then falling back to order_state['waiting_for']
        for self-healing if the former was lost between requests.
        """
        if self.order_status in {
            "awaiting_quantity",
            "awaiting_delivery_method",
            "awaiting_address",
            "awaiting_payment_method",
            "awaiting_customer_name",
            "awaiting_confirmation",
            "awaiting_menu_confirmation",
        }:
            return self.order_status
        if self.order_state.get("waiting_for"):
            return self.order_state["waiting_for"]
        return None

    def pending_item(self) -> dict[str, Any] | None:
        item = self.order_state.get("pending_item")
        return item if isinstance(item, dict) else None

    def set_pending_slot(self, waiting_for: str, pending_item: dict | None = None) -> None:
        """Set a pending slot and optionally the item it refers to."""
        self.order_state["waiting_for"] = waiting_for
        self.order_state["pending_action"] = waiting_for
        if pending_item is not None:
            self.order_state["pending_item"] = pending_item

    def clear_pending_slot(self) -> None:
        self.order_state["waiting_for"] = None
        self.order_state["pending_item"] = None

    def reset_order_state(self) -> None:
        self.order_state = empty_order_state()
        self.order_status = None
        self.payment_method = None
        self.payment_status = None
        self.payment_id = None

    def _clean_name(self, value: str) -> str:
        name = value.strip()
        return re.sub(r"\s+(and|for|to|reserve|book)$", "", name, flags=re.I).strip()
