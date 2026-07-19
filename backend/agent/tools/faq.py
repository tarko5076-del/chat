import re

from agent.tools.base import BaseTool, ToolResult


class FAQTool(BaseTool):
    name = "answer_faq"
    description = "Answer restaurant FAQ questions about hours, address, parking, delivery, Wi-Fi, and payments."
    parameters = {
        "type": "object",
        "properties": {"question": {"type": "string", "description": "The customer question"}},
        "required": ["question"],
    }

    answers = {
        "hours": "We are open daily from 11:00 AM to 10:00 PM.",
        "address": "Our address is 42 Market Street, Downtown.",
        "parking": "Validated parking is available in the Market Street garage after 5:00 PM.",
        "delivery": "We offer delivery within 5 miles through our restaurant team.",
        "wifi": "Free guest Wi-Fi is available. Ask your server for today's password.",
        "payment": "We accept cash, major cards, contactless payments, and gift cards.",
    }

    greetings = {
        "hi", "hello", "hey", "heya", "howdy", "greetings", "good morning",
        "good afternoon", "good evening", "morning", "afternoon", "evening",
        "yo", "sup", "what's up", "whats up", "hey there", "hi there",
        "hello there", "how are you", "how're you", "how you doing",
    }

    def execute(self, **kwargs):
        text = kwargs.get("question", "").lower().strip()

        # FAQ matching FIRST — specific questions always take priority
        if "hour" in text or "open" in text:
            return self._answer("hours")
        if "address" in text or "where" in text or "located" in text:
            return self._answer("address")
        if "park" in text or "parking" in text:
            return self._answer("parking")
        if "deliver" in text or "delivery" in text:
            return self._answer("delivery")
        if "wifi" in text or "wi-fi" in text or "internet" in text:
            return self._answer("wifi")
        if "pay" in text or "card" in text or "cash" in text or "payment" in text:
            return self._answer("payment")

        # Detect thanks / goodbye (catch-all for simple graces)
        if self._is_polite(text):
            return ToolResult(
                success=True,
                message="You're welcome! Let me know if there's anything else I can help you with.",
                data={"response_type": "polite"},
                next_action="ask_user",
            )

        # Detect pure greetings — only if nothing else matched
        if self._is_greeting(text):
            return ToolResult(
                success=True,
                message="Hi there! Welcome to Resto AI. I'm your digital waiter. 😊\n\n"
                        "I can help you browse our menu, place an order, make a reservation, "
                        "or answer any questions. What can I do for you today?",
                data={"response_type": "greeting"},
                next_action="ask_user",
            )

        # Fallback — friendlier than listing dry topics
        return ToolResult(
            success=True,
            message=(
                "I'm happy to help! You can ask me about:\n\n"
                "🍽️  Our menu and recommendations\n"
                "📅  Making a reservation\n"
                "🛵  Placing an order (pickup or delivery)\n"
                "⏰  Opening hours and location\n"
                "❓  Any other questions\n\n"
                "What would you like to know?"
            ),
            data={"known_topics": list(self.answers.keys())},
            next_action="ask_user",
        )

    def _is_greeting(self, text: str) -> bool:
        """Detect if the user is just greeting us.

        Uses exact matching only to avoid false positives
        (e.g. "history" should NOT match "hi").
        """
        clean = re.sub(r"[^a-z'\s]", "", text).strip()
        return clean in self.greetings

    def _is_polite(self, text: str) -> bool:
        """Detect thanks, bye, etc."""
        polite_words = {"thanks", "thank you", "thank", "bye", "goodbye", "see you", "cheers"}
        return any(w in text for w in polite_words)

    def _answer(self, topic):
        return ToolResult(
            success=True,
            message=self.answers[topic],
            data={"topic": topic, "answer": self.answers[topic]},
        )
