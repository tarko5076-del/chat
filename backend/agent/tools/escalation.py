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
        },
        "required": ["reason"],
    }

    async def execute(self, **kwargs):
        reason = kwargs.get("reason", "No reason provided.")
        priority = kwargs.get("priority", "medium")

        logger.info(
            "Escalation requested: priority=%s reason=%s",
            priority,
            reason,
        )

        return ToolResult(
            success=True,
            message="A staff member has been notified and will assist you shortly.",
            data={
                "priority": priority,
                "reason": reason,
                "escalated": True,
            },
        )
