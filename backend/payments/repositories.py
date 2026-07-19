from payments.models import Payment


class PaymentRepository:
    """Database access layer for Payment model."""

    # ── Queries ───────────────────────────────────────────────────────────

    def get_by_id(self, payment_id: int) -> Payment | None:
        return Payment.objects.select_related("order").filter(id=payment_id).first()

    def get_by_order_id(self, order_id: int) -> Payment | None:
        return Payment.objects.filter(order_id=order_id).first()

    def get_by_transaction_ref(self, tx_ref: str) -> Payment | None:
        return Payment.objects.select_related("order").filter(
            transaction_ref=tx_ref
        ).first()

    def get_by_idempotency_key(self, key: str) -> Payment | None:
        return Payment.objects.filter(idempotency_key=key).first()

    def list_by_customer(
        self,
        customer_id: str,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[Payment]:
        qs = Payment.objects.select_related("order").filter(
            order__customer_id=customer_id
        )
        if status:
            qs = qs.filter(status=status)
        return list(qs.order_by("-created_at")[:limit])

    # ── Commands ──────────────────────────────────────────────────────────

    def create_payment(
        self,
        *,
        order,
        provider: str,
        amount: float,
        currency: str = "ETB",
        status: str = "pending",
        idempotency_key: str | None = None,
        customer_email: str = "",
        customer_name: str = "",
    ) -> Payment:
        payment = Payment(
            order=order,
            provider=provider,
            amount=amount,
            currency=currency,
            status=status,
            idempotency_key=idempotency_key,
            customer_email=customer_email,
            customer_name=customer_name,
        )
        payment.save()
        return payment

    def update_status(self, payment: Payment, status: str) -> None:
        Payment.objects.filter(id=payment.id).update(status=status)
        payment.status = status

    def update_checkout_info(
        self,
        payment: Payment,
        *,
        chapa_tx_ref: str,
        checkout_url: str,
        status: str,
    ) -> None:
        Payment.objects.filter(id=payment.id).update(
            chapa_tx_ref=chapa_tx_ref,
            checkout_url=checkout_url,
            status=status,
        )
        payment.chapa_tx_ref = chapa_tx_ref
        payment.checkout_url = checkout_url
        payment.status = status

    def mark_failed(self, payment: Payment, reason: str) -> None:
        Payment.objects.filter(id=payment.id).update(
            status="failed", failure_reason=reason
        )
        payment.status = "failed"
        payment.failure_reason = reason

    def mark_completed(self, payment: Payment) -> None:
        Payment.objects.filter(id=payment.id).update(status="completed")
        payment.status = "completed"
