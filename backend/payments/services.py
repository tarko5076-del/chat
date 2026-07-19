import logging

from django.conf import settings

from orders.models import Order
from payments.chapa_client import ChapaInitResponse, chapa_client
from payments.models import Payment
from payments.repositories import PaymentRepository

logger = logging.getLogger(__name__)


class PaymentServiceError(Exception):
    pass


class PaymentNotFoundError(PaymentServiceError):
    pass


class UnsupportedPaymentMethodError(PaymentServiceError):
    pass


SUPPORTED_METHODS = ["chapa", "telebirr", "cbe_birr", "cash"]


class PaymentService:
    """Business logic for payment processing.

    Supports Chapa (Telebirr, CBE Birr, bank card) and cash payments.
    """

    def __init__(self) -> None:
        self.repo = PaymentRepository()

    # ── Read ──────────────────────────────────────────────────────────────

    def get_payment(self, payment_id: int) -> Payment:
        payment = self.repo.get_by_id(payment_id)
        if not payment:
            raise PaymentNotFoundError(f"Payment #{payment_id} not found.")
        return payment

    def get_payment_by_order(self, order_id: int) -> Payment | None:
        return self.repo.get_by_order_id(order_id)

    def get_payment_by_tx_ref(self, tx_ref: str) -> Payment | None:
        return self.repo.get_by_transaction_ref(tx_ref)

    # ── Write ─────────────────────────────────────────────────────────────

    def initiate_payment(
        self,
        *,
        order: Order,
        payment_method: str,
        customer_email: str,
        customer_name: str = "",
        confirmed: bool = False,
        idempotency_key: str | None = None,
    ) -> tuple[Payment, str | None]:
        """Initiate a payment for an order.

        Returns (payment, checkout_url_or_none).
        For cash payments, the payment is immediately marked completed.
        For Chapa payments, a checkout URL is returned.
        """
        if payment_method not in SUPPORTED_METHODS:
            raise UnsupportedPaymentMethodError(
                f"Supported methods: {', '.join(SUPPORTED_METHODS)}"
            )

        if order.status == "paid":
            raise PaymentServiceError(f"Order #{order.id} has already been paid.")

        # Check idempotency
        if idempotency_key:
            existing = self.repo.get_by_idempotency_key(idempotency_key)
            if existing:
                if existing.status == "completed":
                    return existing, None
                if existing.checkout_url:
                    return existing, existing.checkout_url

        if payment_method == "cash":
            return self._process_cash_payment(
                order=order,
                customer_email=customer_email,
                customer_name=customer_name,
                idempotency_key=idempotency_key,
            )

        return self._process_chapa_payment(
            order=order,
            method=payment_method,
            customer_email=customer_email,
            customer_name=customer_name,
            idempotency_key=idempotency_key,
        )

    def confirm_payment(self, payment: Payment) -> Payment:
        """Check with Chapa API and confirm payment if verified."""
        if payment.status in ("completed", "cancelled"):
            return payment

        if payment.chapa_tx_ref:
            verify_result = chapa_client.verify_payment(payment.chapa_tx_ref)
            if verify_result.success and verify_result.status == "success":
                self.repo.mark_completed(payment)
                return payment
            raise PaymentServiceError("Payment not yet confirmed by provider.")

        if payment.provider == "cash":
            self.repo.mark_completed(payment)
            return payment

        raise PaymentServiceError("Payment not yet confirmed.")

    def verify_and_update(self, tx_ref: str) -> Payment | None:
        """Verify payment status via Chapa API and update local state."""
        payment = self.repo.get_by_transaction_ref(tx_ref)
        if not payment:
            return None

        if payment.status in ("completed", "cancelled"):
            return payment

        if payment.chapa_tx_ref:
            verify_result = chapa_client.verify_payment(payment.chapa_tx_ref)
            if verify_result.success:
                if verify_result.status == "success":
                    self.repo.mark_completed(payment)
                elif verify_result.status in ("failed", "cancelled"):
                    self.repo.mark_failed(payment, verify_result.status)
        return payment

    def mark_failed(self, payment: Payment, reason: str = "") -> None:
        self.repo.mark_failed(payment, reason or "Payment failed")

    # ── Private helpers ───────────────────────────────────────────────────

    def _process_cash_payment(
        self,
        *,
        order: Order,
        customer_email: str,
        customer_name: str,
        idempotency_key: str | None = None,
    ) -> tuple[Payment, None]:
        payment = self.repo.create_payment(
            order=order,
            provider="cash",
            amount=float(order.total),
            status="completed",
            idempotency_key=idempotency_key,
            customer_email=customer_email,
            customer_name=customer_name,
        )
        order.status = "paid"
        order.payment_method = "cash"
        order.save(update_fields=["status", "payment_method"])
        return payment, None

    def _process_chapa_payment(
        self,
        *,
        order: Order,
        method: str,
        customer_email: str,
        customer_name: str,
        idempotency_key: str | None = None,
    ) -> tuple[Payment, str | None]:
        payment = self.repo.create_payment(
            order=order,
            provider=method,
            amount=float(order.total),
            status="pending",
            idempotency_key=idempotency_key,
            customer_email=customer_email,
            customer_name=customer_name,
        )

        base_url = getattr(settings, "FRONTEND_BASE_URL", "http://localhost")
        callback_url = f"{base_url}/api/payments/webhook/chapa/"
        return_url = f"{base_url}/payment/result"

        name_parts = (customer_name or "Customer").split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        init_result = chapa_client.initialize_payment(
            amount=float(order.total),
            email=customer_email,
            first_name=first_name,
            last_name=last_name,
            tx_ref=payment.transaction_ref,
            callback_url=callback_url,
            return_url=return_url,
        )

        if init_result.success:
            self.repo.update_checkout_info(
                payment,
                chapa_tx_ref=init_result.tx_ref or payment.transaction_ref,
                checkout_url=init_result.checkout_url or "",
                status="processing",
            )
            return payment, init_result.checkout_url

        self.repo.mark_failed(payment, init_result.error or "Chapa init failed")
        raise PaymentServiceError(
            f"Could not generate payment link: {init_result.error}. "
            "Please try again or choose a different payment method."
        )
