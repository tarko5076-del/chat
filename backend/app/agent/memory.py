import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from app.tools.base import ToolResult


def empty_order_state() -> dict[str, Any]:
    return {
        "items": [],
        "delivery_method": None,
        "address": None,
        "payment_method": None,
        "status": "collecting_information",
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
    notes: list[str] = field(default_factory=list)

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
        )

    def remember_user_message(self, message: str) -> None:
        self._learn_from_text(message)

    def remember_message(self, message: str) -> None:
        self._learn_from_text(message)

    def remember_tool_result(self, result: ToolResult) -> None:
        for key, value in result.memory_updates.items():
            if hasattr(self, key):
                setattr(self, key, value)
        if result.message:
            self._learn_from_text(result.message)

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
        }

    def _learn_from_text(self, text: str) -> None:
        if match := re.search(r"\bmy name is ([A-Za-z]+(?: [A-Za-z]+)?)", text, re.I):
            self.customer_name = self._clean_name(match.group(1))
        if match := re.search(r"\bfor ([A-Za-z]+(?: [A-Za-z]+)?)", text, re.I):
            self.customer_name = self.customer_name or self._clean_name(match.group(1))
        if match := re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text):
            self.email = match.group(0)
        if match := re.search(r"\b(?:\+?\d[\d .-]{6,}\d)\b", text):
            value = match.group(0)
            lower_text = text.lower()
            is_restaurant_payment_number = "company number" in lower_text or "mobile money" in lower_text
            if not is_restaurant_payment_number and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                self.phone = value
        if match := re.search(r"\bReservation(?: confirmed!)? \(?ID:?\s*(\d+)\)?", text, re.I):
            self.reservation_id = int(match.group(1))
        if match := re.search(r"\bOrder(?: created)? \(?ID:?\s*(\d+)\)?", text, re.I):
            self.order_id = int(match.group(1))
        if party_size := self._party_size(text.lower()):
            self.party_size = party_size
        if res_date := self._date(text.lower()):
            self.reservation_date = res_date
        if res_time := self._time(text.lower()):
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

    def reset_order_state(self) -> None:
        self.order_state = empty_order_state()
        self.order_status = None
        self.payment_method = None
        self.payment_status = None
        self.payment_id = None

    def _party_size(self, text: str) -> int | None:
        match = re.search(r"(?:for|to)\s*(\d+)|(\d+)\s*(?:people|guests|person)", text)
        return int(match.group(1) or match.group(2)) if match else None

    def _clean_name(self, value: str) -> str:
        name = value.strip()
        return re.sub(r"\s+(and|for|to|reserve|book)$", "", name, flags=re.I).strip()

    def _date(self, text: str) -> str | None:
        if "tomorrow" in text:
            return (date.today() + timedelta(days=1)).isoformat()
        if "today" in text:
            return date.today().isoformat()
        match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
        return match.group(0) if match else None

    def _time(self, text: str) -> str | None:
        match = re.search(r"\bat\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text)
        if not match:
            match = re.search(r"\b(\d{1,2})(?::(\d{2}))\s*(am|pm)?\b", text)
        if not match:
            match = re.search(r"\b(\d{1,2})\s*(am|pm)\b", text, re.I)
        if not match:
            # Handle "X hours" as time-of-day (e.g. "3 hours" → 3:00)
            match = re.search(r"\b(\d{1,2})\s*hours?\s*(am|pm)?\b", text, re.I)
        if not match:
            return None
        groups = match.groups()
        hour = int(match.group(1))
        minute = int(groups[1]) if len(groups) > 1 and groups[1] and str(groups[1]).isdigit() else 0
        meridiem = groups[2] if len(groups) > 2 else groups[1]
        if isinstance(meridiem, str) and meridiem.lower() == "pm" and hour < 12:
            hour += 12
        if isinstance(meridiem, str) and meridiem.lower() == "am" and hour == 12:
            hour = 0
        if hour > 23 or minute > 59:
            return None
        return f"{hour:02d}:{minute:02d}"
