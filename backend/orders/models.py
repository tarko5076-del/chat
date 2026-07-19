from decimal import Decimal

from django.db import models


class Order(models.Model):
    DELIVERY_CHOICES = [
        ("delivery", "Delivery"),
        ("pickup", "Pickup"),
        ("dine_in", "Dine In"),
    ]

    PAYMENT_CHOICES = [
        ("cash", "Cash"),
        ("card", "Card"),
        ("telebirr", "TeleBirr"),
        ("cbe_birr", "CBE Birr"),
        ("chapa", "Chapa"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("placed", "Placed"),
        ("preparing", "Preparing"),
        ("served", "Served"),
        ("paid", "Paid"),
        ("cancelled", "Cancelled"),
    ]

    id = models.AutoField(primary_key=True)
    customer_name = models.CharField(max_length=255)
    customer_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")
    delivery_method = models.CharField(max_length=20, choices=DELIVERY_CHOICES, default="delivery")
    delivery_address = models.TextField(blank=True, default="")
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default="cash")
    idempotency_key = models.CharField(max_length=100, unique=True, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "orders"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Order #{self.id} - {self.customer_name}"

    @property
    def subtotal(self):
        return sum(item.quantity * item.price for item in self.items.all())

    @property
    def delivery_fee(self):
        return Decimal("4.99") if self.delivery_method == "delivery" else Decimal("0.00")

    @property
    def total(self):
        return round(self.subtotal * Decimal("1.0825") + self.delivery_fee, 2)

    def to_dict(self):
        return {
            "id": self.id,
            "customer_name": self.customer_name,
            "customer_id": self.customer_id,
            "email": self.email,
            "phone": self.phone,
            "delivery_method": self.delivery_method,
            "delivery_address": self.delivery_address,
            "payment_method": self.payment_method,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "items": [item.to_dict() for item in self.items.all()],
            "subtotal": float(self.subtotal),
            "delivery_fee": float(self.delivery_fee),
            "total": float(self.total),
        }


class OrderItem(models.Model):
    id = models.AutoField(primary_key=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item_id = models.IntegerField()
    item_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "order_items"
        ordering = ["id"]

    def __str__(self):
        return f"{self.quantity}x {self.item_name} (Order #{self.order_id})"

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "menu_item_id": self.menu_item_id,
            "item_name": self.item_name,
            "quantity": self.quantity,
            "price": float(self.price),
            "line_total": float(self.quantity * self.price),
        }
