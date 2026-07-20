"""Multi-turn reservation workflow for the AI Agent.

Guides customers through booking a table step by step:
  date → time → party size → name → phone → email → confirmation

Follows the same state-machine pattern as OrderWorkflow (order_workflow.py).
"""

import re
from datetime import date, time, timedelta
from typing import Any

from agent.memory import ConversationMemory
from agent.utils import (
    parse_date,
    parse_time,
    parse_party_size,
    extract_email,
    extract_phone,
    extract_name,
)


class ReservationWorkflow:
    """State machine for multi-turn reservation creation.

    States:
      idle                   — no active reservation flow
      awaiting_date          — need reservation date
      awaiting_time          — need reservation time
      awaiting_party_size    — need number of guests
      awaiting_customer_name — need customer name
      awaiting_phone         — need phone number
      awaiting_email         — need email address
      awaiting_confirmation  — show summary, ask for confirm
      completed              — reservation created
    """

    cancel_words = frozenset({
        "cancel", "never mind", "forget it", "nothing", "start over",
    })
    confirm_words = frozenset({
        "yes", "yes please", "book", "book it", "book now", "confirm", "confirm it",
        "continue", "proceed", "do it", "okay", "sure", "go ahead",
    })
    decline_words = frozenset({
        "no", "not yet", "change", "edit", "wait", "different",
    })

    # ── Common question starters that indicate a new topic ───────────────
    _new_topic_markers = frozenset({
        "what", "how", "why", "when", "where", "who", "which",
        "can", "could", "would", "will", "do", "does", "did", "is", "are",
        "show", "list", "tell", "give", "recommend",
    })

    def __init__(self, agent: Any) -> None:
        self.agent = agent

    def _message_is_new_topic(self, text: str) -> bool:
        """Check if the message looks like a new question/topic rather than
        a response to the current pending reservation question.

        Returns True for messages starting with question words or
        common request patterns ("what's", "show me", "recommend", etc.).
        """
        first_word = text.split()[0] if text.split() else ""
        first_word = first_word.strip("?'\",.!")

        if first_word in self._new_topic_markers:
            return True

        # Check for common multi-word starters
        if text.startswith(("can i", "can you", "could you", "would you", "do you",
                            "what is", "what's", "what are", "show me",
                            "tell me", "give me", "i want", "i'd like",
                            "i need", "how about")):
            return True

        # Check for new reservation keywords in a non-confirmation context
        has_confirm = any(w in text for w in self.confirm_words)
        has_cancel = any(w in text for w in self.cancel_words)
        if not has_confirm and not has_cancel:
            new_intents = {"menu", "order", "food", "recommend", "recommendation",
                          "suggest", "suggestion", "pay", "payment"}
            if new_intents & set(text.split()):
                return True

        return False

    def _message_relates_to_current_state(self, text: str, status: str) -> bool:
        """Check if the message could plausibly be a response to the current
        pending reservation question.

        This prevents the workflow from stealing messages from other handlers
        when a reservation was started but the user changed the topic.
        """
        # If the user starts a new topic, it doesn't relate to reservation
        if self._message_is_new_topic(text):
            return False

        # Check if the message contains info relevant to the current state
        if status == "awaiting_date":
            return bool(parse_date(text))
        if status == "awaiting_time":
            return bool(parse_time(text))
        if status == "awaiting_party_size":
            import re
            return bool(re.search(r"\d+", text))
        if status == "awaiting_customer_name":
            # Might contain a name — accept if it's not clearly a new topic
            return True
        if status == "awaiting_phone":
            import re
            return bool(re.search(r"\d{5,}", text))
        if status == "awaiting_email":
            return "@" in text
        if status == "awaiting_confirmation":
            # Confirmations are short affirmative/negative words
            has_confirm = any(w in text for w in self.confirm_words)
            has_decline = any(w in text for w in self.decline_words)
            return has_confirm or has_decline

        return True

    # ─────────────────────────────────────────────────────────────────────
    # Main entry point
    # ─────────────────────────────────────────────────────────────────────

    async def handle(self, message: str, memory: ConversationMemory) -> str | None:
        """Process a message through the reservation workflow.

        Returns a response string if this workflow handles the message,
        or None to let the planner/LLM handle it.
        """
        text = message.lower().strip()
        status = getattr(memory, "reservation_status", None)

        # Only handle if we have a pending reservation or explicit intent
        has_reservation_context = self._has_reservation_context(text, memory)
        if not status and not has_reservation_context:
            return None

        # Cancel handler — always checked first, even before the new-topic guard
        if self._is_cancel(text):
            return self._cancel_reservation(memory)

        # If we have a pending status, check that the message relates to it
        # — prevents the workflow from stealing unrelated messages
        if status and not self._message_relates_to_current_state(text, status):
            return None

        # Route to current state handler
        if status == "awaiting_date":
            return await self._handle_date(text, memory)
        if status == "awaiting_time":
            return await self._handle_time(text, memory)
        if status == "awaiting_party_size":
            return self._handle_party_size(text, memory)
        if status == "awaiting_customer_name":
            return self._handle_name(text, message, memory)
        if status == "awaiting_phone":
            return self._handle_phone(text, memory)
        if status == "awaiting_email":
            return self._handle_email(text, memory)
        if status == "awaiting_confirmation":
            return await self._handle_confirmation(text, memory)

        # New reservation request — try to extract all info at once
        if has_reservation_context and not status:
            return await self._start_reservation(text, message, memory)

        return None

    # ─────────────────────────────────────────────────────────────────────
    # State handlers
    # ─────────────────────────────────────────────────────────────────────

    async def _start_reservation(
        self, text: str, message: str, memory: ConversationMemory,
    ) -> str:
        """Start a new reservation flow, extracting any info we can."""
        # Collect all available info from the message
        res_date = parse_date(text) or ""
        res_time = parse_time(text) or ""
        party_size = parse_party_size(text)
        cust_name = extract_name(message)
        phone = extract_phone(text)
        email = extract_email(text)

        # Store what we found
        if res_date:
            memory.reservation_date = res_date
        if res_time:
            memory.reservation_time = res_time
        if party_size:
            memory.party_size = party_size
        if cust_name:
            memory.customer_name = cust_name
        if phone:
            memory.phone = phone
        if email:
            memory.email = email

        # If we have a date and time, check availability proactively
        if res_date and res_time:
            available, msg = await self._check_slot(res_date, res_time, party_size or 2)
            if not available:
                memory.reservation_date = None
                memory.reservation_time = None
                return self._slot_unavailable_response(msg, res_date, res_time)

        # Ask for next missing field
        return self._prompt_next(memory)

    async def _handle_date(self, text: str, memory: ConversationMemory) -> str:
        res_date = parse_date(text)
        if not res_date:
            return (
                "I didn't catch the date. When would you like to come? "
                "For example, 'tomorrow' or '2026-07-20'."
            )
        memory.reservation_date = res_date

        # If we also have time, check availability
        if memory.reservation_time:
            available, msg = await self._check_slot(
                res_date, memory.reservation_time, memory.party_size or 2,
            )
            if not available:
                memory.reservation_date = None
                memory.reservation_time = None
                return self._slot_unavailable_response(msg, res_date, memory.reservation_time)

        return self._prompt_next(memory)

    async def _handle_time(self, text: str, memory: ConversationMemory) -> str:
        res_time = parse_time(text)
        if not res_time:
            return (
                "I didn't catch the time. What time would you like to arrive? "
                "For example, '7pm' or '19:00'."
            )
        memory.reservation_time = res_time

        # Check availability
        res_date = memory.reservation_date
        if res_date:
            available, msg = await self._check_slot(
                res_date, res_time, memory.party_size or 2,
            )
            if not available:
                memory.reservation_time = None
                return self._slot_unavailable_response(msg, res_date, res_time)

        return self._prompt_next(memory)

    def _handle_party_size(self, text: str, memory: ConversationMemory) -> str:
        # Try to extract party size more aggressively
        size = parse_party_size(text)
        if not size:
            size_match = re.search(r"\b(\d+)\b", text)
            if size_match:
                size = int(size_match.group(1))
        
        # Log for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Party size extraction: text='{text}', extracted_size={size}")
        
        if not size or size < 1:
            return "How many guests will be joining? (Please give me a number.)"

        from reservations.models import MAX_PARTY_SIZE
        if size > MAX_PARTY_SIZE:
            memory.party_size = None
            return (
                f"For parties over {MAX_PARTY_SIZE}, please call the restaurant "
                "directly so we can arrange the best seating for you."
            )

        memory.party_size = size
        logger.info(f"Party size set to: {size}")
        return self._prompt_next(memory)

    def _handle_name(self, text: str, message: str, memory: ConversationMemory) -> str:
        cust_name = extract_name(message) or extract_name(text)
        if not cust_name:
            return "What name should I book the reservation under?"
        memory.customer_name = cust_name
        return self._prompt_next(memory)

    def _handle_phone(self, text: str, memory: ConversationMemory) -> str:
        phone = extract_phone(text) or text.strip()
        if not phone or len(phone) < 5:
            return "Please provide a phone number so we can reach you if needed."
        memory.phone = phone
        return self._prompt_next(memory)

    def _handle_email(self, text: str, memory: ConversationMemory) -> str:
        email = extract_email(text)
        if not email:
            return "Please provide an email address for the confirmation."
        memory.email = email
        return self._prompt_next(memory)

    async def _handle_confirmation(
        self, text: str, memory: ConversationMemory,
    ) -> str:
        if self._is_decline(text):
            return self._cancel_reservation(memory)

        if not self._is_confirmation(text):
            return self._confirmation_prompt(memory) + "\n\nWould you like me to book this table?"

        # User confirmed — create and confirm the reservation directly
        return await self._create_and_confirm_reservation(memory)

    # ─────────────────────────────────────────────────────────────────────
    # Slot-availability check
    # ─────────────────────────────────────────────────────────────────────

    async def _check_slot(
        self, res_date: str, res_time: str, party_size: int,
    ) -> tuple[bool, str]:
        """Check if a time slot is available. Returns (available, message)."""
        result = await self.agent._execute_tool(
            "manage_reservation",
            {
                "action": "check",
                "reservation_date": res_date,
                "reservation_time": res_time,
                "party_size": party_size,
            },
            ConversationMemory(),
        )
        if result.success:
            return True, "Available."
        return False, result.message

    def _slot_unavailable_response(
        self, msg: str, res_date: str, res_time: str,
    ) -> str:
        """Suggest nearby alternatives when a slot is full."""
        fallback = (
            f"{msg}\n\n"
            "Would you like to try a different time or date?"
        )

        # Try to parse the time and suggest nearby slots
        try:
            parts = res_time.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        except (ValueError, IndexError):
            return fallback

        from reservations.models import OPENING_HOUR, CLOSING_HOUR

        alternatives = []
        # Check 30min before and after
        for delta_min in [-60, -30, 30, 60]:
            alt_hour = hour + (minute + delta_min) // 60
            alt_min = (minute + delta_min) % 60
            if alt_hour < OPENING_HOUR or alt_hour >= CLOSING_HOUR:
                continue
            alt_time = f"{alt_hour:02d}:{alt_min:02d}"
            alternatives.append(alt_time)
            if len(alternatives) >= 3:
                break

        if not alternatives:
            return fallback

        alt_text = ", ".join(alternatives)
        return (
            f"{msg}\n\n"
            f"Would {alt_text} work for you instead?"
        )

    # ─────────────────────────────────────────────────────────────────────
    # Reservation creation
    # ─────────────────────────────────────────────────────────────────────

    async def _create_reservation(self, memory: ConversationMemory) -> str:
        """Create the reservation via the ReservationTool."""
        result = await self.agent._execute_tool(
            "manage_reservation",
            {
                "action": "create",
                "customer_name": memory.customer_name or "Guest",
                "customer_id": memory.customer_id,
                "phone": memory.phone or "",
                "email": memory.email or "",
                "reservation_date": memory.reservation_date,
                "reservation_time": memory.reservation_time,
                "party_size": memory.party_size,
            },
            memory,
        )

        if not result.success:
            return result.message

        # Set status to held so user can confirm
        memory.reservation_status = "held"

        return result.message

    async def _create_and_confirm_reservation(self, memory: ConversationMemory) -> str:
        """Create and confirm the reservation directly in one step."""
        # First create the reservation
        result = await self.agent._execute_tool(
            "manage_reservation",
            {
                "action": "create",
                "customer_name": memory.customer_name or "Guest",
                "customer_id": memory.customer_id,
                "phone": memory.phone or "",
                "email": memory.email or "",
                "reservation_date": memory.reservation_date,
                "reservation_time": memory.reservation_time,
                "party_size": memory.party_size,
            },
            memory,
        )

        if not result.success:
            return result.message

        # Immediately confirm it
        confirm_result = await self.agent._execute_tool(
            "manage_reservation",
            {
                "action": "confirm",
                "reservation_id": memory.reservation_id,
            },
            memory,
        )

        if not confirm_result.success:
            return f"{result.message}\n\nHowever, confirmation failed: {confirm_result.message}"

        memory.reservation_status = "completed"

        # Send confirmation email
        if memory.email:
            try:
                from django.core.mail import send_mail
                from django.conf import settings
                send_mail(
                    subject="Reservation Confirmed",
                    message=(
                        f"Hi {memory.customer_name or 'Guest'},\n\n"
                        f"Your reservation is confirmed:\n"
                        f"  Date: {memory.reservation_date}\n"
                        f"  Time: {memory.reservation_time}\n"
                        f"  Guests: {memory.party_size}\n\n"
                        f"Reservation ID: {memory.reservation_id}\n\n"
                        "We look forward to serving you!\n"
                        f"{getattr(settings, 'RESTAURANT_NAME', 'The Restaurant')}"
                    ),
                    from_email=getattr(
                        settings, "DEFAULT_FROM_EMAIL", "noreply@restaurant.com"
                    ),
                    recipient_list=[memory.email],
                    fail_silently=True,
                )
            except Exception:
                import logging
                logging.getLogger(__name__).debug(
                    "Failed to send reservation confirmation", exc_info=True
                )

        return (
            f"✅ Your reservation is confirmed!\n\n"
            f"  {memory.customer_name or 'Guest'}, "
            f"{memory.party_size} guests\n"
            f"  {memory.reservation_date} at {memory.reservation_time}\n"
            f"  Reservation ID: {memory.reservation_id}\n\n"
            "A confirmation email has been sent. We look forward to seeing you!"
        )

    # ─────────────────────────────────────────────────────────────────────
    # Cancel / reset
    # ─────────────────────────────────────────────────────────────────────

    def _cancel_reservation(self, memory: ConversationMemory) -> str:
        memory.reservation_status = None
        memory.reservation_date = None
        memory.reservation_time = None
        memory.party_size = None
        return "No problem. I've cancelled the reservation request. Let me know if you'd like to try a different time!"

    # ─────────────────────────────────────────────────────────────────────
    # Prompt helpers
    # ─────────────────────────────────────────────────────────────────────

    def _prompt_next(self, memory: ConversationMemory) -> str:
        """Ask for the next missing piece of info."""
        if not memory.reservation_date:
            memory.reservation_status = "awaiting_date"
            return "Great! What date would you like to book? (For example, 'tomorrow' or a specific date.)"

        if not memory.reservation_time:
            memory.reservation_status = "awaiting_time"
            return f"Perfect, {memory.reservation_date}! What time would you like to arrive?"

        if not memory.party_size:
            memory.reservation_status = "awaiting_party_size"
            return "How many guests will be joining you?"

        if not memory.customer_name:
            memory.reservation_status = "awaiting_customer_name"
            return "What name should I book the reservation under?"

        if not memory.phone:
            memory.reservation_status = "awaiting_phone"
            return "Please provide a phone number so we can reach you if needed."

        if not memory.email:
            memory.reservation_status = "awaiting_email"
            return "What email address should I send the confirmation to?"

        # Everything collected — show summary
        memory.reservation_status = "awaiting_confirmation"
        return self._confirmation_prompt(memory) + "\n\nShall I book this table?"

    def _confirmation_prompt(self, memory: ConversationMemory) -> str:
        return (
            "📋 **Reservation Summary**\n\n"
            f"  Date: {memory.reservation_date}\n"
            f"  Time: {memory.reservation_time}\n"
            f"  Guests: {memory.party_size or 'Not specified'}\n"
            f"  Name: {memory.customer_name or 'Not specified'}\n"
            f"  Phone: {memory.phone or 'Not specified'}\n"
            f"  Email: {memory.email or 'Not specified'}"
        )

    # ─────────────────────────────────────────────────────────────────────
    # Intent detection helpers
    # ─────────────────────────────────────────────────────────────────────

    def _has_reservation_context(self, text: str, memory: ConversationMemory) -> bool:
        """Detect if the user is making a reservation request."""
        # Explicit reservation keywords
        reservation_keywords = {
            "reserve", "reservation", "book", "booking", "table",
        }
        if any(w in text for w in reservation_keywords):
            return True

        # Check if date/time/party size look like reservation intent
        # and we're not in the middle of something else
        if memory.order_status and memory.order_status != "completed":
            return False

        has_date = bool(parse_date(text))
        has_time = bool(parse_time(text))
        has_party = bool(parse_party_size(text))

        # A message with date+time+party is almost certainly a reservation
        if has_date and has_time:
            return True
        if has_date and has_party:
            return True

        return False

    def _is_cancel(self, text: str) -> bool:
        return any(w in text for w in self.cancel_words)

    def _is_confirmation(self, text: str) -> bool:
        return any(w in text for w in self.confirm_words)

    def _is_decline(self, text: str) -> bool:
        return any(w in text for w in self.decline_words)
