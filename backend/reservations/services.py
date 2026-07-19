import logging
from datetime import date, time, timedelta

from django.utils import timezone

from reservations.models import (
    Reservation,
    MAX_PARTY_SIZE,
    MAX_RESERVATIONS_PER_SLOT,
    OPENING_HOUR,
    CLOSING_HOUR,
    RESERVATION_HOLD_MINUTES,
)
from reservations.repositories import ReservationRepository

logger = logging.getLogger(__name__)


class ReservationServiceError(Exception):
    pass


class ReservationNotFoundError(ReservationServiceError):
    pass


class SlotUnavailableError(ReservationServiceError):
    pass


class MissingFieldError(ReservationServiceError):
    pass


class ReservationService:
    """Business logic for reservation management."""

    def __init__(self) -> None:
        self.repo = ReservationRepository()
        self.opening_time = time(OPENING_HOUR, 0)
        self.closing_time = time(CLOSING_HOUR, 0)

    # ── Read ──────────────────────────────────────────────────────────────

    def get_reservation(self, reservation_id: int) -> Reservation:
        reservation = self.repo.get_by_id(reservation_id)
        if not reservation:
            raise ReservationNotFoundError(
                f"Reservation #{reservation_id} not found."
            )
        return reservation

    def list_by_customer(
        self,
        customer_id: str,
        *,
        status: str | None = None,
    ) -> list[Reservation]:
        return self.repo.list_by_customer(customer_id, status=status)

    def list_by_status(self, status: str) -> list[Reservation]:
        return self.repo.list_all_by_status(status)

    # ── Availability ──────────────────────────────────────────────────────

    def check_availability(
        self,
        *,
        reservation_date: date,
        reservation_time: time,
        party_size: int = 2,
    ) -> tuple[bool, str]:
        """Check if a slot is available. Returns (available, reason)."""
        if party_size < 1:
            return False, "Party size must be at least 1 guest."
        if party_size > MAX_PARTY_SIZE:
            return False, (
                f"For parties over {MAX_PARTY_SIZE}, please call the restaurant directly."
            )
        if reservation_time < self.opening_time or reservation_time >= self.closing_time:
            return False, (
                f"That time is outside our hours of {OPENING_HOUR}:00 to {CLOSING_HOUR}:00."
            )

        # Release expired holds first
        self.repo.release_expired_holds(reservation_date, reservation_time)

        existing = self.repo.count_active_for_slot(reservation_date, reservation_time)
        if existing >= MAX_RESERVATIONS_PER_SLOT:
            return False, (
                f"Sorry, no tables are available on {reservation_date} "
                f"at {reservation_time.strftime('%H:%M')}."
            )
        return True, "Available."

    # ── Write ─────────────────────────────────────────────────────────────

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
    ) -> Reservation:
        """Create a new reservation with an initial 'held' status."""
        available, reason = self.check_availability(
            reservation_date=reservation_date,
            reservation_time=reservation_time,
            party_size=party_size,
        )
        if not available:
            raise SlotUnavailableError(reason)

        now = timezone.now()
        reservation = self.repo.create_reservation(
            customer_name=customer_name,
            customer_id=customer_id,
            phone=phone,
            email=email,
            reservation_date=reservation_date,
            reservation_time=reservation_time,
            party_size=party_size,
            status="held",
            held_until=now + timedelta(minutes=RESERVATION_HOLD_MINUTES),
        )
        logger.info(
            "action=create reservation_id=%d party_size=%d date=%s time=%s status=held",
            reservation.id, party_size, reservation_date, reservation_time,
        )
        return reservation

    def confirm_reservation(self, reservation_id: int) -> Reservation:
        """Confirm a held reservation (with row-level lock)."""
        reservation = self.repo.get_for_update(reservation_id)
        if not reservation:
            raise ReservationNotFoundError(f"Reservation #{reservation_id} not found.")

        if reservation.is_held_expired:
            self.repo.update_status(reservation, "cancelled")
            raise SlotUnavailableError(
                f"Reservation #{reservation_id} has expired. "
                f"Holds are released after {RESERVATION_HOLD_MINUTES} minutes."
            )

        if reservation.status == "confirmed":
            return reservation

        if reservation.status != "held":
            raise ReservationServiceError(
                f"Cannot confirm reservation in '{reservation.status}' status."
            )

        # Re-check availability with the lock held
        self.repo.release_expired_holds(
            reservation.reservation_date, reservation.reservation_time
        )
        available, _ = self.check_availability(
            reservation_date=reservation.reservation_date,
            reservation_time=reservation.reservation_time,
            party_size=reservation.party_size,
        )
        # Our own reservation counts, so check with exclude
        existing = self.repo.count_active_for_slot(
            reservation.reservation_date,
            reservation.reservation_time,
            exclude_id=reservation.id,
        )
        if existing >= MAX_RESERVATIONS_PER_SLOT:
            raise SlotUnavailableError(
                "That time slot is now full. Please choose a different time."
            )

        self.repo.confirm_reservation(reservation)
        logger.info("action=confirm reservation_id=%d status=confirmed", reservation.id)
        return reservation

    def update_reservation(
        self,
        reservation_id: int,
        **updates,
    ) -> Reservation:
        """Update reservation fields, re-checking availability if time/size changed."""
        reservation = self.repo.get_by_id(reservation_id)
        if not reservation:
            raise ReservationNotFoundError(f"Reservation #{reservation_id} not found.")

        candidate_date = updates.get("reservation_date", reservation.reservation_date)
        candidate_time = updates.get("reservation_time", reservation.reservation_time)
        candidate_size = updates.get("party_size", reservation.party_size)

        if isinstance(candidate_date, str):
            candidate_date = date.fromisoformat(candidate_date)
        if isinstance(candidate_time, str):
            candidate_time = time.fromisoformat(candidate_time)

        changed = (
            candidate_date != reservation.reservation_date
            or candidate_time != reservation.reservation_time
            or candidate_size != reservation.party_size
        )

        if changed:
            available, reason = self.check_availability(
                reservation_date=candidate_date,
                reservation_time=candidate_time,
                party_size=candidate_size,
            )
            if not available:
                raise SlotUnavailableError(reason)

        if "customer_name" in updates:
            reservation.customer_name = updates["customer_name"]
        if "phone" in updates:
            reservation.phone = updates["phone"]
        if "email" in updates:
            reservation.email = updates["email"]
        if "reservation_date" in updates:
            reservation.reservation_date = candidate_date
        if "reservation_time" in updates:
            reservation.reservation_time = candidate_time
        if "party_size" in updates:
            reservation.party_size = int(updates["party_size"])

        reservation.save()
        return reservation

    def cancel_reservation(self, reservation_id: int) -> Reservation:
        reservation = self.repo.get_by_id(reservation_id)
        if not reservation:
            raise ReservationNotFoundError(f"Reservation #{reservation_id} not found.")
        self.repo.update_status(reservation, "cancelled")
        logger.info("action=cancel reservation_id=%d status=cancelled", reservation.id)
        return reservation
