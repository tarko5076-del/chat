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

    def execute(self, **kwargs):
        text = kwargs.get("question", "").lower()
        if "hour" in text or "open" in text:
            return self._answer("hours")
        if "address" in text or "where" in text:
            return self._answer("address")
        if "park" in text:
            return self._answer("parking")
        if "deliver" in text:
            return self._answer("delivery")
        if "wifi" in text or "wi-fi" in text:
            return self._answer("wifi")
        if "pay" in text or "card" in text or "cash" in text:
            return self._answer("payment")
        return ToolResult(
            success=True,
            message=(
                "I can help with opening hours, address, parking, delivery, Wi-Fi, "
                "payment methods, menu, reservations, orders, and bills."
            ),
            data={"known_topics": list(self.answers.keys())},
            next_action="ask_user",
        )

    def _answer(self, topic):
        return ToolResult(
            success=True,
            message=self.answers[topic],
            data={"topic": topic, "answer": self.answers[topic]},
        )
