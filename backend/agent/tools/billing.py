from agent.tools.base import BaseTool, ToolResult, TAX_RATE
from orders.models import Order


class BillingTool(BaseTool):
    name = "calculate_bill"
    description = "Calculate subtotal, tax, total, and optional split amount for an order."
    parameters = {
        "type": "object",
        "properties": {
            "order_id": {"type": "integer"},
            "customer_name": {"type": "string"},
            "split_count": {"type": "integer", "minimum": 2},
        },
    }

    def execute(self, **kwargs):
        order = self._find_order(kwargs)
        if not order:
            return ToolResult(
                success=False,
                message="I could not find an active order to calculate.",
                missing_fields=["order_id"],
                next_action="ask_user",
            )
        items_list = list(order.items.all())
        subtotal = sum(item.price * item.quantity for item in items_list)
        tax = subtotal * TAX_RATE
        total = subtotal + tax
        lines = [
            f"Bill for order ID: {order.id}",
            f"Subtotal: ${subtotal:.2f}",
            f"Tax: ${tax:.2f}",
            f"Total: ${total:.2f}",
        ]
        if split_count := kwargs.get("split_count"):
            lines.append(f"Split {split_count} ways: ${total / int(split_count):.2f} each")
        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={
                "order_id": order.id,
                "subtotal": float(subtotal),
                "tax": float(tax),
                "total": float(total),
                "split_count": kwargs.get("split_count"),
                "split_amount": total / int(kwargs["split_count"]) if kwargs.get("split_count") else None,
            },
            memory_updates={"order_id": order.id, "customer_name": order.customer_name},
        )

    def _find_order(self, kwargs):
        if order_id := kwargs.get("order_id"):
            return Order.objects.filter(id=order_id).first()
        name = kwargs.get("customer_name") or "Guest"
        return Order.objects.filter(customer_name=name, status="active").first()
