from rest_framework import permissions, viewsets

from orders.models import Order
from orders.serializers import OrderSerializer, OrderCreateSerializer
from orders.services import OrderService


class OrderViewSet(viewsets.ModelViewSet):
    """Order management — requires authentication, scoped to the current user.

    If the user has a role of 'staff' or 'admin', they can view all orders.
    Regular customers can only see and manage their own orders.
    """
    permission_classes = [permissions.IsAuthenticated]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = OrderService()

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        return OrderSerializer

    def get_queryset(self):
        qs = Order.objects.prefetch_related("items").all()
        user = self.request.user

        # Staff/admin can see all orders (useful for the staff dashboard)
        if user.role in ("staff", "admin"):
            status_filter = self.request.query_params.get("status")
            if status_filter:
                qs = qs.filter(status=status_filter)
            return qs.order_by("-created_at")

        # Regular customers see only their own orders
        qs = qs.filter(customer_id=str(user.id))
        status_filter = self.request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs.order_by("-created_at")
