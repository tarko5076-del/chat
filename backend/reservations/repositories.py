from datetime import date, time
from django.utils import timezone

from reservations.models import Reservation


class ReservationRepository:
    """Database access layer for Reservation model."""

    # ── Queries ───────────────────────────────────────────────────────────

    def get_by_id(self, reservation_id: int) -> Reservation | None:
        return Reservation.objects.filter(id=reservation_id).first()

    def get_for_update(self, reservation_id: int) -> Reservation | None:
        """Lock the row for update (used during confirmation to prevent double-booking)."""
        from django.db import transaction
        with transaction.atomic():
            return (
                Reservation.objects
                .select_for_update()
                .filter(id=reservation_id)
                .first()
            )

    def count_active_for_slot(
        self,
        res_date: date,
        res_time: time,
        *,
        exclude_id: int | None = None,
    ) -> int:
        qs = Reservation.objects.filter(
            reservation_date=res_date,
            reservation_time=res_time,
            status__in=["confirmed", "held"],
        )
        if exclude_id:
            qs = qs.exclude(id=exclude_id)
        return qs.count()

    def list_by_customer(
        self,
        customer_id: str,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[Reservation]:
        qs = Reservation.objects.filter(customer_id=customer_id)
        if status:
            qs = qs.filter(status=status)
        return list(qs.order_by("-created_at")[:limit])

    def list_all_by_status(self, status: str, *, limit: int = 50) -> list[Reservation]:
        return list(Reservation.objects.filter(status=status)[:limit])

    # ── Commands ──────────────────────────────────────────────────────────

    def create_reservation(
        self,
        *,
        customer_name: str,
        customer_id: str | None = None,
        phone: str,
        email: str,
        reservation_date: date,
        reservation_time: time,
        party_size: int,
        status: str = "held",
        held_until=None,
    ) -> Reservation:
        reservation = Reservation(
            customer_name=customer_name,
            customer_id=customer_id,
            phone=phone,
            email=email,
            reservation_date=reservation_date,
            reservation_time=reservation_time,
            party_size=party_size,
            status=status,
            held_until=held_until,
        )
        reservation.save()
        return reservation

    def update_status(self, reservation: Reservation, status: str) -> None:
        Reservation.objects.filter(id=reservation.id).update(status=status)
        reservation.status = status

    def confirm_reservation(self, reservation: Reservation) -> None:
        Reservation.objects.filter(id=reservation.id).update(
            status="confirmed", held_until=None
        )
        reservation.status = "confirmed"
        reservation.held_until = None

    def release_expired_holds(self, res_date: date, res_time: time) -> int:
        """Release all expired held reservations for a given slot. Returns count released."""
        now = timezone.now()
        count = Reservation.objects.filter(
            reservation_date=res_date,
            reservation_time=res_time,
            status="held",
            held_until__lte=now,
        ).update(status="cancelled")
        return count
