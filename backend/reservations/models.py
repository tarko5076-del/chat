from django.db import models
from django.utils import timezone

MAX_PARTY_SIZE = 12
MAX_RESERVATIONS_PER_SLOT = 10
OPENING_HOUR = 11
CLOSING_HOUR = 22


class Reservation(models.Model):
    STATUS_CHOICES = [
        ("held", "Held"),
        ("confirmed", "Confirmed"),
        ("seated", "Seated"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    id = models.AutoField(primary_key=True)
    customer_name = models.CharField(max_length=255)
    customer_id = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    reservation_date = models.DateField()
    reservation_time = models.TimeField()
    party_size = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="confirmed")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reservations"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Reservation #{self.id} - {self.customer_name} ({self.reservation_date} {self.reservation_time})"

    def to_dict(self):
        return {
            "id": self.id,
            "customer_name": self.customer_name,
            "customer_id": self.customer_id,
            "phone": self.phone,
            "email": self.email,
            "reservation_date": self.reservation_date.isoformat() if self.reservation_date else None,
            "reservation_time": self.reservation_time.isoformat() if self.reservation_time else None,
            "party_size": self.party_size,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
