import hashlib
import hmac
import json
import logging
import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .chapa_client import chapa_client
from .models import Payment
from .serializers import PaymentCreateSerializer, PaymentSerializer

logger = logging.getLogger(__name__)

_WEBHOOK_TIMESTAMP_MAX_AGE = 300
_WEBHOOK_RATE_LIMIT = 10
_WEBHOOK_RATE_WINDOW = 60


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
        if payment.status not in ("pending", "processing"):
            return Response(
                {"error": f"Payment is already {payment.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if payment.chapa_tx_ref:
            verify_result = chapa_client.verify_payment(payment.chapa_tx_ref)
            if verify_result.success and verify_result.status == "success":
                payment.status = "completed"
                payment.save(update_fields=["status", "updated_at"])
                payment.order.status = "paid"
                payment.order.save(update_fields=["status"])
                return Response(PaymentSerializer(payment).data)
            return Response(
                {"error": "Payment not yet confirmed by Chapa. Please wait or retry."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if payment.provider == "cash":
            payment.status = "completed"
            payment.save(update_fields=["status", "updated_at"])
            payment.order.status = "paid"
            payment.order.payment_method = "cash"
            payment.order.save(update_fields=["status", "payment_method"])
            return Response(PaymentSerializer(payment).data)

        return Response(
            {"error": "Payment not yet confirmed. Please wait for provider confirmation."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    @action(detail=True, methods=["post"])
    def fail(self, request, pk=None):
        payment = self.get_object()
        if payment.status not in ("pending", "processing"):
            return Response(
                {"error": f"Payment is already {payment.status}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        payment.status = "failed"
        payment.failure_reason = request.data.get("reason", "Marked as failed")
        payment.save(update_fields=["status", "failure_reason", "updated_at"])
        return Response(PaymentSerializer(payment).data)

    @action(detail=True, methods=["get"])
    def check_status(self, request, pk=None):
        payment = self.get_object()
        if payment.status in ("completed", "cancelled"):
            return Response({
                "status": payment.status,
                "transaction_ref": payment.transaction_ref,
            })

        if payment.chapa_tx_ref:
            verify_result = chapa_client.verify_payment(payment.chapa_tx_ref)
            if verify_result.success:
                if verify_result.status == "success":
                    payment.status = "completed"
                    payment.save(update_fields=["status", "updated_at"])
                    payment.order.status = "paid"
                    payment.order.save(update_fields=["status"])
                elif verify_result.status in ("failed", "cancelled"):
                    payment.status = "failed"
                    payment.failure_reason = verify_result.status
                    payment.save(update_fields=["status", "failure_reason", "updated_at"])

        return Response({
            "status": payment.status,
            "transaction_ref": payment.transaction_ref,
        })


def _verify_chapa_signature(body_bytes: bytes) -> bool:
    """Verify webhook authenticity by calling Chapa's verify endpoint."""
    try:
        body = json.loads(body_bytes)
    except (json.JSONDecodeError, ValueError):
        return False

    tx_ref = body.get("tx_ref")
    if not tx_ref:
        return False

    verify_result = chapa_client.verify_payment(tx_ref)
    return verify_result.success and verify_result.status == body.get("status")


@csrf_exempt
@require_POST
def chapa_webhook(request):
    """Handle Chapa payment callback webhook.

    Security: After basic format validation, we verify the payment status
    by calling Chapa's verify endpoint before trusting the payload.
    This prevents forged webhooks from marking payments as complete.
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return HttpResponseBadRequest("Invalid JSON")

    tx_ref = body.get("tx_ref")
    status_str = body.get("status")

    if not tx_ref:
        return HttpResponseBadRequest("Missing tx_ref")

    ip = request.META.get("REMOTE_ADDR", "unknown")
    rate_key = f"chapa_webhook:{ip}"
    hits = cache.get(rate_key, 0)
    if hits >= _WEBHOOK_RATE_LIMIT:
        logger.warning("Chapa webhook rate limit exceeded for %s", ip)
        return HttpResponse(status=429)
    cache.set(rate_key, hits + 1, _WEBHOOK_RATE_WINDOW)

    logger.info("Chapa webhook received: tx_ref=%s status=%s", tx_ref, status_str)

    try:
        payment = Payment.objects.select_related("order").get(transaction_ref=tx_ref)
    except Payment.DoesNotExist:
        logger.warning("Chapa webhook for unknown tx_ref: %s", tx_ref)
        return HttpResponse(status=200)

    verify_result = chapa_client.verify_payment(tx_ref)
    if not verify_result.success:
        logger.warning(
            "Chapa webhook verification failed for tx_ref=%s: %s",
            tx_ref, verify_result.error,
        )
        return HttpResponse(status=200)

    verified_status = verify_result.status
    if verified_status != status_str:
        logger.warning(
            "Chapa webhook status mismatch: payload=%s verified=%s tx_ref=%s",
            status_str, verified_status, tx_ref,
        )
        status_str = verified_status

    if status_str == "success":
        payment.status = "completed"
        payment.save(update_fields=["status", "updated_at"])
        payment.order.status = "paid"
        payment.order.save(update_fields=["status"])
        logger.info("Payment %s completed via webhook", tx_ref)
    elif status_str in ("failed", "cancelled"):
        payment.status = "failed"
        payment.failure_reason = f"Chapa callback: {status_str}"
        payment.save(update_fields=["status", "failure_reason", "updated_at"])
        logger.info("Payment %s failed via webhook: %s", tx_ref, status_str)

    return HttpResponse(status=200)
