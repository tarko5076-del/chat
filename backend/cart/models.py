from django.db import models


class Cart(models.Model):
    """Temporary shopping session before order confirmation."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("converted", "Converted to Order"),
        ("abandoned", "Abandoned"),
    ]

    customer_id = models.CharField(max_length=255, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cart"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["customer_id", "status"]),
        ]

    def __str__(self):
        return f"Cart #{self.id} ({self.customer_id})"

    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "status": self.status,
            "items": [item.to_dict() for item in self.items.all()],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CartItem(models.Model):
    """Individual item inside a shopping cart."""

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    menu_item_id = models.IntegerField()
    item_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "cart_items"
        ordering = ["id"]

    def __str__(self):
        return f"{self.quantity}x {self.item_name} (Cart #{self.cart_id})"

    def to_dict(self):
        return {
            "id": self.id,
            "cart_id": self.cart_id,
            "menu_item_id": self.menu_item_id,
            "item_name": self.item_name,
            "quantity": self.quantity,
            "unit_price": float(self.unit_price),
            "line_total": float(self.quantity * self.unit_price),
            "notes": self.notes,
        }
