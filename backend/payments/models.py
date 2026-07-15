import uuid

from django.db import models


class Payment(models.Model):
    PROVIDER_CHOICES = [
        ("chapa", "Chapa"),
        ("telebirr", "Telebirr"),
        ("cbe_birr", "CBE Birr"),
        ("card", "Card"),
        ("mobile_money", "Mobile Money"),
        ("cash", "Cash"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.AutoField(primary_key=True)
    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="payment",
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="ETB")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    transaction_ref = models.CharField(
        max_length=100, unique=True, editable=False,
        default=None, null=True, blank=True,
    )
    chapa_tx_ref = models.CharField(
        max_length=200, blank=True, default="",
        help_text="Chapa transaction reference for verification",
    )
    checkout_url = models.URLField(
        max_length=500, blank=True, default="",
        help_text="Chapa checkout URL for user redirect",
    )
    idempotency_key = models.CharField(
        max_length=100, unique=True, null=True, blank=True,
    )
    customer_email = models.EmailField(blank=True, default="")
    customer_name = models.CharField(max_length=255, blank=True, default="")
    failure_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payments"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment #{self.id} - Order #{self.order_id} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.transaction_ref:
            self.transaction_ref = f"pay_{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)
