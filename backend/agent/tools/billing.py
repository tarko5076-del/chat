import logging

from orders.services import OrderService, OrderNotFoundError
from agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class BillingTool(BaseTool):
    name = "calculate_bill"
    description = "Calculate subtotal, tax, total, and optional split amount for an order."
    parameters = {
        "type": "object",
        "properties": {
            "order_id": {"type": "integer"},
            "customer_name": {"type": "string"},
        },
        "additionalProperties": {
            "split_count": {"type": "integer", "minimum": 2},
        },
    }

    def __init__(self):
        super().__init__()
        self.service = OrderService()

    def execute(self, **kwargs):
        order = self._find_order(kwargs)
        if not order:
            return ToolResult(
                success=False,
                message="I could not find an active order to calculate.",
                missing_fields=["order_id"],
                next_action="ask_user",
            )

        totals = self.service.calculate_total(order)
        lines = [
            f"Bill for order ID: {order.id}",
            f"Subtotal: ${totals.subtotal:.2f}",
            f"Tax: ${totals.tax:.2f}",
            f"Total: ${totals.total:.2f}",
        ]

        split_count = kwargs.get("split_count")
        if split_count:
            lines.append(f"Split {split_count} ways: ${totals.total / int(split_count):.2f} each")

        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={
                "order_id": order.id,
                "subtotal": totals.subtotal,
                "tax": totals.tax,
                "total": totals.total,
                "split_count": split_count,
                "split_amount": totals.total / int(split_count) if split_count else None,
            },
            memory_updates={"order_id": order.id, "customer_name": order.customer_name},
        )

    def _find_order(self, kwargs):
        order_id = kwargs.get("order_id")
        if order_id:
            try:
                return self.service.get_order(order_id)
            except OrderNotFoundError:
                return None

        name = kwargs.get("customer_name") or "Guest"
        return self.service.get_active_order(customer_name=name)
