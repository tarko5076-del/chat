from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Payment
from .serializers import PaymentCreateSerializer, PaymentSerializer


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related("order").all()
    serializer_class = PaymentSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
    ]
    filterset_fields = ["order_id", "status"]
    ordering_fields = ["created_at", "amount"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == "create":
            return PaymentCreateSerializer
        return PaymentSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        payment = self.get_object()
        if payment.status != "pending":
            return Response(
                {"error": "Only pending payments can be confirmed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        payment.status = "completed"
        payment.save(update_fields=["status"])
        return Response(PaymentSerializer(payment).data)

    @action(detail=True, methods=["post"])
    def fail(self, request, pk=None):
        payment = self.get_object()
        if payment.status != "pending":
            return Response(
                {"error": "Only pending payments can be marked as failed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        payment.status = "failed"
        payment.save(update_fields=["status"])
        return Response(PaymentSerializer(payment).data)
