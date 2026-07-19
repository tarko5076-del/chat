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

from payments.models import Payment
from payments.serializers import PaymentCreateSerializer, PaymentSerializer
from payments.services import PaymentService, PaymentServiceError

logger = logging.getLogger(__name__)

_WEBHOOK_TIMESTAMP_MAX_AGE = 300
_WEBHOOK_RATE_LIMIT = 10
_WEBHOOK_RATE_WINDOW = 60


class PaymentViewSet(viewsets.ModelViewSet):
    """Payment management — requires authentication, scoped to the current user.

    Staff/admin can see all payments. Customers see only payments for their orders.
    The Chapa webhook endpoint is public (no auth) because Chapa signs requests.
    """
    queryset = Payment.objects.select_related("order").all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["order_id", "status"]
    ordering_fields = ["created_at", "amount"]
    ordering = ["-created_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = PaymentService()

    def get_serializer_class(self):
        if self.action == "create":
            return PaymentCreateSerializer
        return PaymentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.role in ("staff", "admin"):
            return qs

        # Regular customers see only payments for their orders
        return qs.filter(order__customer_id=str(user.id))

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
        try:
            payment = self.service.confirm_payment(payment)
            return Response(PaymentSerializer(payment).data)
        except PaymentServiceError as e:
            return Response(
                {"error": str(e)},
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
        self.service.mark_failed(payment, request.data.get("reason", "Marked as failed"))
        return Response(PaymentSerializer(payment).data)

    @action(detail=True, methods=["get"])
    def check_status(self, request, pk=None):
        payment = self.get_object()
        payment = self.service.verify_and_update(payment.transaction_ref) or payment
        return Response({
            "status": payment.status,
            "transaction_ref": payment.transaction_ref,
        })


def _verify_chapa_hmac(body_bytes: bytes, signature_header: str | None) -> bool:
    """Verify webhook authenticity via HMAC-SHA256 signature."""
    webhook_secret = getattr(settings, "CHAPA_WEBHOOK_SECRET", "")
    if not webhook_secret:
        return True  # No secret configured — HMAC verification is opt-in.

    if not signature_header:
        logger.warning("Chapa webhook missing x-chapa-signature header")
        return False

    expected = hmac.new(
        webhook_secret.encode("utf-8"),
        body_bytes,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@csrf_exempt
@require_POST
def chapa_webhook(request):
    """Handle Chapa payment callback webhook — public endpoint (HMAC-authenticated)."""
    # ── Step 1: HMAC signature verification ───────────────────────────────
    raw_body = request.body
    signature = (
        request.META.get("HTTP_X_CHAPA_SIGNATURE")
        or request.META.get("HTTP_CHAPA_SIGNATURE")
    )
    if not _verify_chapa_hmac(raw_body, signature):
        logger.warning("Chapa webhook HMAC verification failed — rejecting")
        return HttpResponse(status=401)

    # ── Step 2: Parse payload ─────────────────────────────────────────────
    try:
        body = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError):
        return HttpResponseBadRequest("Invalid JSON")

    tx_ref = body.get("tx_ref")
    status_str = body.get("status")

    if not tx_ref:
        return HttpResponseBadRequest("Missing tx_ref")

    # ── Step 3: Rate limiting ──────────────────────────────────────────────
    ip = request.META.get("REMOTE_ADDR", "unknown")
    rate_key = f"chapa_webhook:{ip}"
    hits = cache.get(rate_key, 0)
    if hits >= _WEBHOOK_RATE_LIMIT:
        logger.warning("Chapa webhook rate limit exceeded for %s", ip)
        return HttpResponse(status=429)
    cache.set(rate_key, hits + 1, _WEBHOOK_RATE_WINDOW)

    logger.info("Chapa webhook received: tx_ref=%s status=%s", tx_ref, status_str)

    # ── Step 4: Update via service ─────────────────────────────────────────
    svc = PaymentService()
    payment = svc.verify_and_update(tx_ref)
    if not payment:
        logger.warning("Chapa webhook for unknown tx_ref: %s", tx_ref)

    return HttpResponse(status=200)
