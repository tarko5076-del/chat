from datetime import date, time, timedelta

from django.db import transaction
from django.utils import timezone

from agent.tools.base import BaseTool, ToolResult
from reservations.models import Reservation, MAX_PARTY_SIZE, MAX_RESERVATIONS_PER_SLOT, OPENING_HOUR, CLOSING_HOUR, RESERVATION_HOLD_MINUTES


class ReservationTool(BaseTool):
    name = "manage_reservation"
    description = "Check, create, confirm, update, cancel, or list restaurant reservations."
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["check", "create", "confirm", "update", "cancel", "list"]},
            "reservation_id": {"type": "integer"},
            "customer_name": {"type": "string"},
            "phone": {"type": "string"},
            "email": {"type": "string"},
            "reservation_date": {"type": "string", "description": "YYYY-MM-DD"},
            "reservation_time": {"type": "string", "description": "HH:MM"},
            "party_size": {"type": "integer"},
        },
        "required": ["action"],
    }

    opening_time = time(OPENING_HOUR, 0)
    closing_time = time(CLOSING_HOUR, 0)

    def execute(self, **kwargs):
        action = kwargs["action"]
        try:
            if action == "check":
                return self._check_availability(kwargs)
            if action == "create":
                return self._create_reservation(kwargs)
            if action == "confirm":
                return self._confirm_reservation(kwargs)
            if action == "update":
                return self._update_reservation(kwargs)
            if action == "cancel":
                return self._cancel_reservation(kwargs)
            if action == "list":
                return self._list_reservations(kwargs)
        except ValueError as error:
            return ToolResult(
                success=False,
                message=f"I could not use that reservation detail: {error}.",
                next_action="ask_user",
            )
        return ToolResult(success=False, message=f"Unknown reservation action: {action}.")

    def _check_availability(self, kwargs):
        missing = self._missing(kwargs, ["reservation_date", "reservation_time"])
        if missing:
            return self._missing_result(missing)
        res_date = date.fromisoformat(kwargs["reservation_date"])
        res_time = time.fromisoformat(kwargs["reservation_time"])
        party_size = int(kwargs.get("party_size") or 2)

        # Auto-release expired holds for this slot
        self._release_expired_holds(res_date, res_time)

        available, reason = self._slot_available(res_date, res_time, party_size)
        if available:
            return ToolResult(
                success=True,
                message=f"Tables are available on {res_date} at {res_time.strftime('%H:%M')} for {party_size} guests.",
                data={
                    "available": True,
                    "reservation_date": res_date.isoformat(),
                    "reservation_time": res_time.strftime("%H:%M"),
                    "party_size": party_size,
                },
                memory_updates={
                    "reservation_date": res_date.isoformat(),
                    "reservation_time": res_time.strftime("%H:%M"),
                    "party_size": party_size,
                },
            )
        return ToolResult(
            success=False,
            message=reason,
            data={
                "available": False,
                "reservation_date": res_date.isoformat(),
                "reservation_time": res_time.strftime("%H:%M"),
                "party_size": party_size,
            },
            next_action="ask_user",
        )

    def _create_reservation(self, kwargs):
        required = ["customer_name", "phone", "email", "reservation_date", "reservation_time", "party_size"]
        if missing := self._missing(kwargs, required):
            return self._missing_result(missing)
        res_date = date.fromisoformat(kwargs["reservation_date"])
        res_time = time.fromisoformat(kwargs["reservation_time"])
        party_size = int(kwargs["party_size"])

        # Auto-release expired holds for this slot
        self._release_expired_holds(res_date, res_time)

        available, reason = self._slot_available(res_date, res_time, party_size)
        if not available:
            return ToolResult(
                success=False,
                message=reason,
                data={
                    "available": False,
                    "reservation_date": res_date.isoformat(),
                    "reservation_time": res_time.strftime("%H:%M"),
                    "party_size": party_size,
                },
                next_action="ask_user",
            )
        now = timezone.now()
        reservation = Reservation(
            customer_name=kwargs["customer_name"],
            phone=kwargs["phone"],
            email=kwargs["email"],
            reservation_date=res_date,
            reservation_time=res_time,
            party_size=party_size,
            status="held",
            held_until=now + timedelta(minutes=RESERVATION_HOLD_MINUTES),
        )
        reservation.save()
        memory_updates = {
            "customer_name": reservation.customer_name,
            "phone": reservation.phone,
            "email": reservation.email,
            "reservation_id": reservation.id,
            "reservation_date": reservation.reservation_date.isoformat(),
            "reservation_time": reservation.reservation_time.strftime("%H:%M"),
            "party_size": reservation.party_size,
        }
        return ToolResult(
            success=True,
            message=(
                f"Reservation held! ID: {reservation.id}. {reservation.customer_name}, "
                f"{reservation.party_size} guests on {reservation.reservation_date} "
                f"at {reservation.reservation_time.strftime('%H:%M')}. "
                f"This hold expires in {RESERVATION_HOLD_MINUTES} minutes. "
                f"Please confirm the reservation to secure your table."
            ),
            data={"reservation": reservation.to_dict()},
            memory_updates=memory_updates,
        )

    def _update_reservation(self, kwargs):
        reservation = self._get_reservation(kwargs.get("reservation_id"))
        if isinstance(reservation, ToolResult):
            return reservation
        candidate_date = date.fromisoformat(kwargs["reservation_date"]) if kwargs.get("reservation_date") else reservation.reservation_date
        candidate_time = time.fromisoformat(kwargs["reservation_time"]) if kwargs.get("reservation_time") else reservation.reservation_time
        candidate_size = int(kwargs.get("party_size") or reservation.party_size)
        available, reason = self._slot_available(
            candidate_date,
            candidate_time,
            candidate_size,
            exclude_reservation_id=reservation.id,
        )
        if not available:
            return ToolResult(
                success=False,
                message=reason,
                data={
                    "available": False,
                    "reservation_id": reservation.id,
                    "reservation_date": candidate_date.isoformat(),
                    "reservation_time": candidate_time.strftime("%H:%M"),
                    "party_size": candidate_size,
                },
                next_action="ask_user",
            )
        self._apply_updates(reservation, kwargs)
        reservation.save()
        return ToolResult(
            success=True,
            message=f"Reservation {reservation.id} updated successfully.",
            data={"reservation": reservation.to_dict()},
            memory_updates={
                "reservation_id": reservation.id,
                "customer_name": reservation.customer_name,
                "phone": reservation.phone,
                "email": reservation.email,
                "reservation_date": reservation.reservation_date.isoformat(),
                "reservation_time": reservation.reservation_time.strftime("%H:%M"),
                "party_size": reservation.party_size,
            },
        )

    def _confirm_reservation(self, kwargs):
        reservation_id = kwargs.get("reservation_id")
        if not reservation_id:
            return self._missing_result(["reservation_id"])

        # select_for_update prevents concurrent double-booking
        with transaction.atomic():
            reservation = (
                Reservation.objects
                .select_for_update()
                .filter(id=reservation_id)
                .first()
            )
            if not reservation:
                return ToolResult(
                    success=False,
                    message=f"Reservation with ID {reservation_id} was not found.",
                    next_action="ask_user",
                )

            if reservation.is_held_expired:
                reservation.status = "cancelled"
                reservation.save(update_fields=["status"])
                return ToolResult(
                    success=False,
                    message=(
                        f"Reservation {reservation_id} has expired. "
                        f"Holds are released after {RESERVATION_HOLD_MINUTES} minutes. "
                        f"Would you like to create a new reservation?"
                    ),
                    data={"reservation_id": reservation_id, "status": "cancelled"},
                    next_action="ask_user",
                )

            if reservation.status == "confirmed":
                return ToolResult(
                    success=True,
                    message=f"Reservation {reservation_id} is already confirmed.",
                    data={"reservation": reservation.to_dict()},
                )

            if reservation.status not in ("held",):
                return ToolResult(
                    success=False,
                    message=f"Cannot confirm reservation in '{reservation.status}' status.",
                    data={"reservation_id": reservation_id, "status": reservation.status},
                    next_action="ask_user",
                )

            # Check slot capacity again with lock held
            self._release_expired_holds(reservation.reservation_date, reservation.reservation_time)
            available, reason = self._slot_available(
                reservation.reservation_date,
                reservation.reservation_time,
                reservation.party_size,
                exclude_reservation_id=reservation.id,
            )
            if not available:
                return ToolResult(
                    success=False,
                    message=f"Cannot confirm: {reason}",
                    data={"reservation_id": reservation_id},
                    next_action="ask_user",
                )

            reservation.status = "confirmed"
            reservation.held_until = None
            reservation.save(update_fields=["status", "held_until"])

        return ToolResult(
            success=True,
            message=(
                f"Reservation {reservation.id} confirmed! {reservation.customer_name}, "
                f"{reservation.party_size} guests on {reservation.reservation_date} "
                f"at {reservation.reservation_time.strftime('%H:%M')}."
            ),
            data={"reservation": reservation.to_dict()},
            memory_updates={"reservation_id": reservation.id},
        )

    def _cancel_reservation(self, kwargs):
        reservation = self._get_reservation(kwargs.get("reservation_id"))
        if isinstance(reservation, ToolResult):
            return reservation
        reservation.status = "cancelled"
        reservation.save()
        return ToolResult(
            success=True,
            message=f"Reservation {reservation.id} has been cancelled.",
            data={"reservation_id": reservation.id, "status": reservation.status},
            memory_updates={"reservation_id": None},
        )

    def _list_reservations(self, kwargs):
        query = Reservation.objects.filter(status="confirmed")
        if name := kwargs.get("customer_name"):
            query = query.filter(customer_name__icontains=name)
        reservations = list(query.order_by("reservation_date"))
        if not reservations:
            return ToolResult(success=True, message="No active reservations found.", data={"reservations": []})
        lines = ["Active reservations:"]
        for reservation in reservations:
            lines.append(
                f"- ID {reservation.id}: {reservation.customer_name}, "
                f"{reservation.party_size} guests on {reservation.reservation_date} "
                f"at {reservation.reservation_time.strftime('%H:%M')}"
            )
        return ToolResult(
            success=True,
            message="\n".join(lines),
            data={"reservations": [reservation.to_dict() for reservation in reservations]},
        )

    def _apply_updates(self, reservation, kwargs):
        if name := kwargs.get("customer_name"):
            reservation.customer_name = name
        if phone := kwargs.get("phone"):
            reservation.phone = phone
        if email := kwargs.get("email"):
            reservation.email = email
        if res_date := kwargs.get("reservation_date"):
            reservation.reservation_date = date.fromisoformat(res_date)
        if res_time := kwargs.get("reservation_time"):
            reservation.reservation_time = time.fromisoformat(res_time)
        if party_size := kwargs.get("party_size"):
            reservation.party_size = int(party_size)

    def _get_reservation(self, reservation_id):
        if not reservation_id:
            return self._missing_result(["reservation_id"])
        reservation = Reservation.objects.filter(id=reservation_id).first()
        if reservation:
            return reservation
        return ToolResult(
            success=False,
            message=f"Reservation with ID {reservation_id} was not found.",
            next_action="ask_user",
        )

    def _missing(self, kwargs, fields):
        return [field for field in fields if kwargs.get(field) in (None, "")]

    def _missing_result(self, fields):
        return ToolResult(
            success=False,
            message=f"Missing required fields: {', '.join(fields)}.",
            missing_fields=fields,
            next_action="ask_user",
        )

    def _slot_available(self, reservation_date, reservation_time, party_size, exclude_reservation_id=None):
        if party_size < 1:
            return False, "Party size must be at least 1 guest."
        if party_size > MAX_PARTY_SIZE:
            return False, f"For parties over {MAX_PARTY_SIZE}, please call the restaurant directly."
        if reservation_time < self.opening_time or reservation_time >= self.closing_time:
            return False, f"That time is outside our opening hours of {OPENING_HOUR}:00 AM to {CLOSING_HOUR}:00 PM."

        query = Reservation.objects.filter(
            reservation_date=reservation_date,
            reservation_time=reservation_time,
            status__in=["confirmed", "held"],
        )
        if exclude_reservation_id:
            query = query.exclude(id=exclude_reservation_id)
        existing = query.count()
        if existing >= MAX_RESERVATIONS_PER_SLOT:
            return False, (
                f"Sorry, no tables are available on {reservation_date} "
                f"at {reservation_time.strftime('%H:%M')}."
            )
        return True, "Available."

    def _release_expired_holds(self, reservation_date, reservation_time):
        """Release all expired held reservations for a given slot."""
        now = timezone.now()
        expired = Reservation.objects.filter(
            reservation_date=reservation_date,
            reservation_time=reservation_time,
            status="held",
            held_until__lte=now,
        )
        count = expired.update(status="cancelled")
        if count:
            from reservations.models import logger as reservations_logger
            reservations_logger.info(
                "Released %d expired holds for %s %s",
                count, reservation_date, reservation_time,
            )
