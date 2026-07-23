import logging
from agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class StartOrderWorkflowTool(BaseTool):
    name = "start_order_workflow"
    description = (
        "Start or continue the food ordering workflow. "
        "Use this when the user clearly wants to place an order, add items to an order, "
        "or is in the middle of a multi-step ordering process."
    )

    def __init__(self, agent):
        self._agent = agent

    def execute(self, **kwargs):
        message = getattr(self._agent, "_current_message", None)
        memory = getattr(self._agent, "_current_memory", None)
        if not message or not memory:
            return ToolResult(
                success=False,
                message="No active conversation context available.",
            )
        from asgiref.sync import async_to_sync
        result = async_to_sync(self._agent.order_workflow.handle)(message, memory)
        if result is None:
            return ToolResult(
                success=False,
                message="I cannot handle this as an ordering request. Try asking the user what they'd like.",
            )
        return ToolResult(success=True, message=result)


class StartReservationWorkflowTool(BaseTool):
    name = "start_reservation_workflow"
    description = (
        "Start or continue the table reservation workflow. "
        "Use this when the user clearly wants to book a table, make a reservation, "
        "or is in the middle of a multi-step reservation process."
    )

    def __init__(self, agent):
        self._agent = agent

    def execute(self, **kwargs):
        message = getattr(self._agent, "_current_message", None)
        memory = getattr(self._agent, "_current_memory", None)
        if not message or not memory:
            return ToolResult(
                success=False,
                message="No active conversation context available.",
            )
        from asgiref.sync import async_to_sync
        result = async_to_sync(self._agent.reservation_workflow.handle)(message, memory)
        if result is None:
            return ToolResult(
                success=False,
                message="I cannot handle this as a reservation request. Try asking the user what they'd like.",
            )
        return ToolResult(success=True, message=result)
