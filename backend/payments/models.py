import uuid

from django.db import models


class Payment(models.Model):
    PROVIDER_CHOICES = [
        ("card", "Card"),
        ("mobile_money", "Mobile Money"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    id = models.AutoField(primary_key=True)
    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="payment",
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    transaction_ref = models.CharField(
        max_length=100, unique=True, editable=False,
        default=None, null=True, blank=True,
    )
    idempotency_key = models.CharField(
        max_length=100, unique=True, null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "payments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment #{self.id} - Order #{self.order_id} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.transaction_ref:
            self.transaction_ref = f"pay_{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)
