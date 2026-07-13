import re
from datetime import date, timedelta
from typing import Any

from app.agent.memory import ConversationMemory


class LocalPlanner:
    def plan(self, message: str, memory: ConversationMemory) -> list[dict[str, Any]]:
        text = message.lower()
        has_explicit_keyword = self._has_explicit_intent_keyword(text)

        # 1. Explicit intent keywords — these take priority over everything else.
        #    Must run BEFORE context-aware follow-up checks because memory
        #    may have been populated with reservation-like fields from the
        #    same message (e.g. "Show today's menu" extracts "today" as a date).
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

        # 2. Context-aware follow-ups for messages that continue a flow
        #    but do NOT contain explicit intent keywords.
        if not has_explicit_keyword:
            if self._provides_reservation_followup(text, memory):
                return [{"tool": "manage_reservation", "args": self._reservation_args(text, memory)}]

            if self._refers_to_existing_reservation(text, memory):
                return [{"tool": "manage_reservation", "args": self._reservation_args(text, memory)}]

            if memory.current_order_items() and self._provides_order_followup(text, memory):
                return [{"tool": "manage_order", "args": self._order_args(message, memory)}]

        # 3. Fallback — if we are in any reservation or order flow
        if self._has_reservation_context(memory):
            return [{"tool": "manage_reservation", "args": self._reservation_args(text, memory)}]

        if memory.current_order_items():
            return [{"tool": "manage_order", "args": self._order_args(message, memory)}]

        return [{"tool": "answer_faq", "args": {"question": message}}]

    def _has_explicit_intent_keyword(self, text: str) -> bool:
        """Check if the message contains any top-level intent keyword."""
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
        """Return True if the conversation has any pending reservation details."""
        return bool(
            memory.party_size
            or memory.reservation_date
            or memory.reservation_time
            or memory.reservation_id
        )

    def _provides_reservation_followup(self, text: str, memory: ConversationMemory) -> bool:
        """Detect follow-up messages that provide details for a pending reservation."""
        if not self._has_reservation_context(memory):
            return False
        if memory.reservation_id:
            return False  # reservation is already confirmed
        has_contact = "@" in text or self._looks_like_phone(text) or "my name is" in text
        has_time = bool(self._time(text))
        has_date = bool(self._date(text))
        return has_contact or has_time or has_date

    def _provides_order_followup(self, text: str, memory: ConversationMemory) -> bool:
        """Detect follow-up messages for an ongoing order flow."""
        if not memory.current_order_items():
            return False
        has_delivery = any(word in text for word in ["pickup", "delivery", "collect"])
        has_payment = any(
            word in text
            for word in ["card", "cash", "mobile", "gift", "mpesa"]
        )
        return has_delivery or has_payment

    def _looks_like_phone(self, text: str) -> bool:
        """Check if text looks like a phone number."""
        digits = re.sub(r"[^\d]", "", text)
        return 7 <= len(digits) <= 15

    def _refers_to_existing_reservation(self, text: str, memory: ConversationMemory) -> bool:
        action = any(word in text for word in ["change", "update", "modify", "cancel"])
        return bool(memory.reservation_id and action)

    def _is_faq(self, text: str) -> bool:
        # Do NOT treat "hour" as FAQ if it looks like a time expression
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
        if size := self._party_size(text):
            args["party_size"] = size
        elif memory.party_size:
            args["party_size"] = memory.party_size
        if res_date := self._date(text):
            args["reservation_date"] = res_date
        elif memory.reservation_date:
            args["reservation_date"] = memory.reservation_date
        if res_time := self._time(text):
            args["reservation_time"] = res_time
        elif memory.reservation_time:
            args["reservation_time"] = memory.reservation_time

        # Extract contact info from message text (not just memory)
        if raw_email := self._extract_email(text):
            args["email"] = raw_email
        elif memory.email:
            args["email"] = memory.email

        if raw_phone := self._extract_phone(text):
            args["phone"] = raw_phone
        elif memory.phone:
            args["phone"] = memory.phone

        if raw_name := self._extract_name(text):
            args["customer_name"] = raw_name
        elif memory.customer_name:
            args["customer_name"] = memory.customer_name

        return args

    def _extract_email(self, text: str) -> str | None:
        match = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text)
        return match.group(0) if match else None

    def _extract_phone(self, text: str) -> str | None:
        # Match the actual phone number, not the surrounding text
        match = re.search(r"\b(?:\+?\d[\d .-]{6,}\d)\b", text)
        if match:
            value = match.group(0)
            # Exclude date-like patterns (XXXX-XX-XX)
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                return value.strip()
        return None

    def _extract_name(self, text: str) -> str | None:
        match = re.search(r"(?:my name is|name is|it's|it is|i am|i'm)\s+([A-Za-z]+(?: [A-Za-z]+)?)", text, re.I)
        if match:
            return match.group(1).strip().title()
        match = re.search(r"\bfor\s+([A-Za-z]+(?: [A-Za-z]+)?)\b", text, re.I)
        if match:
            name = match.group(1).strip()
            if name.lower() not in {"dinner", "lunch", "breakfast", "tonight", "tomorrow", "today"}:
                return name.title()
        # Fallback: bare single name (e.g. "tarko" without "my name is")
        stripped = text.strip()
        if re.fullmatch(r"[A-Za-z]+(?:['-][A-Za-z]+)?", stripped, re.I):
            common = {"yes", "no", "ok", "okay", "please", "thanks", "hello", "hi", "hey", "help"}
            if stripped.lower() not in common:
                return stripped.title()
        return None

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

    def _party_size(self, text: str) -> int | None:
        match = re.search(r"(?:for|to)\s*(\d+)|(\d+)\s*(?:people|guests|person)", text)
        return int(match.group(1) or match.group(2)) if match else None

    def _quantity(self, text: str) -> int:
        match = re.search(r"\b(\d+)\b", text)
        return int(match.group(1)) if match else 1

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
            match = re.search(r"\b(\d{1,2})\s*(am|pm)\b", text)
        if not match:
            # Handle "3pm" without space
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
