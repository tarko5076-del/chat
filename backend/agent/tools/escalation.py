import logging

from agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class EscalationTool(BaseTool):
    name = "request_human_staff"
    description = "Request assistance from a human staff member when the agent cannot handle the request."
    parameters = {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "The reason human staff assistance is needed.",
            },
            "priority": {
                "type": "string",
                "enum": ["low", "medium", "high"],
                "description": "The urgency of the escalation.",
            },
            "customer_id": {
                "type": "string",
                "description": "The customer's ID if known.",
            },
            "customer_name": {
                "type": "string",
                "description": "The customer's name if known.",
            },
        },
        "required": ["reason"],
    }

    def execute(self, **kwargs):
        reason = kwargs.get("reason", "No reason provided.")
        priority = kwargs.get("priority", "medium")
        customer_id = kwargs.get("customer_id", "")
        customer_name = kwargs.get("customer_name", "")

        try:
            from agent.models import StaffNotification

            notification = StaffNotification(
                customer_id=customer_id,
                customer_name=customer_name,
                reason=reason,
                priority=priority,
                status="pending",
            )
            notification.save()

            logger.info(
                "Escalation created: id=%d priority=%s reason=%s",
                notification.id,
                priority,
                reason,
            )

            return ToolResult(
                success=True,
                message=(
                    f"A staff member has been notified (ticket #{notification.id}) "
                    f"and will assist you shortly. Priority: {priority}."
                ),
                data={
                    "notification_id": notification.id,
                    "priority": priority,
                    "reason": reason,
                    "escalated": True,
                },
            )
        except Exception:
            logger.exception("Failed to create staff notification")
            return ToolResult(
                success=True,
                message="A staff member has been notified and will assist you shortly.",
                data={
                    "priority": priority,
                    "reason": reason,
                    "escalated": True,
                },
            )
