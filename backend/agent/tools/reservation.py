import logging
from datetime import date, time

from reservations.services import (
    ReservationService,
    ReservationServiceError,
    ReservationNotFoundError,
    SlotUnavailableError,
    MissingFieldError,
)
from agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class ReservationTool(BaseTool):
    name = "manage_reservation"
    description = "Check, create, confirm, update, cancel, or list restaurant reservations."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["check", "create", "confirm", "update", "cancel", "list"],
            },
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

    def __init__(self):
        super().__init__()
        self.service = ReservationService()

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
        except ValueError as e:
            return ToolResult(
                success=False,
                message=f"I could not use that reservation detail: {e}.",
                next_action="ask_user",
            )
        except (ReservationServiceError, SlotUnavailableError) as e:
            return ToolResult(
                success=False,
                message=str(e),
                next_action="ask_user",
            )

        return ToolResult(success=False, message=f"Unknown reservation action: {action}.")

    def _find_nearby_slots(self, res_time: time) -> list[str]:
        """Find nearby available time slots (30-min increments before/after)."""
        from reservations.models import OPENING_HOUR, CLOSING_HOUR
        suggestions = []
        for delta_min in [-60, -30, 30, 60]:
            total_minutes = res_time.hour * 60 + res_time.minute + delta_min
            alt_hour = total_minutes // 60
            alt_min = total_minutes % 60
            if alt_hour < OPENING_HOUR or alt_hour >= CLOSING_HOUR:
                continue
            suggestions.append(f"{alt_hour:02d}:{alt_min:02d}")
            if len(suggestions) >= 3:
                break
        return suggestions

    def _check_availability(self, kwargs):
        missing = self._missing(kwargs, ["reservation_date", "reservation_time"])
        if missing:
            return self._missing_result(missing)

        res_date = date.fromisoformat(kwargs["reservation_date"])
        res_time = time.fromisoformat(kwargs["reservation_time"])
        party_size = int(kwargs.get("party_size", 2))

        available, reason = self.service.check_availability(
            reservation_date=res_date,
            reservation_time=res_time,
            party_size=party_size,
        )

        if available:
            return ToolResult(
                success=True,
                message=(
                    f"Tables are available on {res_date} at {res_time.strftime('%H:%M')} "
                    f"for {party_size} guests."
                ),
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

        # Slot full — find nearby alternatives
        nearby = self._find_nearby_slots(res_time)
        if nearby:
            alt_text = ", ".join(nearby)
            message = (
                f"{reason}\n\n"
                f"Would {alt_text} work for you instead?"
            )
        else:
            message = f"{reason}\n\nWould you like to try a different time or date?"

        return ToolResult(
            success=False,
            message=message,
            data={
                "available": False,
                "available_slots": nearby,
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

        reservation = self.service.create_reservation(
            customer_name=kwargs["customer_name"],
            phone=kwargs["phone"],
            email=kwargs["email"],
            reservation_date=date.fromisoformat(kwargs["reservation_date"]),
            reservation_time=time.fromisoformat(kwargs["reservation_time"]),
            party_size=int(kwargs["party_size"]),
        )

        memory_updates = {
            "customer_name": reservation.customer_name,
            "phone": reservation.phone,
            "email": reservation.email,
            "reservation_id": reservation.id,
            "reservation_date": reservation.reservation_date.isoformat(),
            "reservation_time": reservation.reservation_time.strftime("%H:%M"),
            "party_size": reservation.party_size,
        }

        from reservations.models import RESERVATION_HOLD_MINUTES

        # Record business event for monitoring
        try:
            from config.monitoring import record_business_event
            record_business_event("reservations")
        except ImportError:
            pass

        return ToolResult(
            success=True,
            message=(
                f"Reservation held! ID: {reservation.id}. {reservation.customer_name}, "
                f"{reservation.party_size} guests on {reservation.reservation_date} "
                f"at {reservation.reservation_time.strftime('%H:%M')}. "
                f"This hold expires in {RESERVATION_HOLD_MINUTES} minutes. "
                "Please confirm the reservation to secure your table."
            ),
            data={"reservation": reservation.to_dict()},
            memory_updates=memory_updates,
        )

    def _confirm_reservation(self, kwargs):
        reservation_id = kwargs.get("reservation_id")
        if not reservation_id:
            return self._missing_result(["reservation_id"])

        reservation = self.service.confirm_reservation(int(reservation_id))

        # Send email confirmation
        try:
            from django.core.mail import send_mail
            from django.conf import settings
            if reservation.email:
                send_mail(
                    subject="Reservation Confirmed",
                    message=(
                        f"Hi {reservation.customer_name},\n\n"
                        f"Your reservation is confirmed:\n"
                        f"  Date: {reservation.reservation_date}\n"
                        f"  Time: {reservation.reservation_time.strftime('%H:%M')}\n"
                        f"  Guests: {reservation.party_size}\n"
                        f"  Reservation ID: {reservation.id}\n\n"
                        "We look forward to serving you!"
                    ),
                    from_email=getattr(
                        settings, "DEFAULT_FROM_EMAIL", "noreply@restaurant.com"
                    ),
                    recipient_list=[reservation.email],
                    fail_silently=True,
                )
        except Exception:
            import logging
            logging.getLogger(__name__).debug(
                "Failed to send reservation confirmation email", exc_info=True
            )

        # Record business event for monitoring
        try:
            from config.monitoring import record_business_event
            record_business_event("reservations")
        except ImportError:
            pass

        return ToolResult(
            success=True,
            message=(
                f"Reservation {reservation.id} confirmed! {reservation.customer_name}, "
                f"{reservation.party_size} guests on {reservation.reservation_date} "
                f"at {reservation.reservation_time.strftime('%H:%M')}. "
                "A confirmation email has been sent."
            ),
            data={"reservation": reservation.to_dict()},
            memory_updates={
                "reservation_id": reservation.id,
                "customer_name": reservation.customer_name,
                "phone": reservation.phone,
                "email": reservation.email,
            },
        )

    def _update_reservation(self, kwargs):
        reservation_id = kwargs.get("reservation_id")
        if not reservation_id:
            return self._missing_result(["reservation_id"])

        updates = {}
        if kwargs.get("customer_name"):
            updates["customer_name"] = kwargs["customer_name"]
        if kwargs.get("phone"):
            updates["phone"] = kwargs["phone"]
        if kwargs.get("email"):
            updates["email"] = kwargs["email"]
        if kwargs.get("reservation_date"):
            updates["reservation_date"] = kwargs["reservation_date"]
        if kwargs.get("reservation_time"):
            updates["reservation_time"] = kwargs["reservation_time"]
        if kwargs.get("party_size"):
            updates["party_size"] = int(kwargs["party_size"])

        reservation = self.service.update_reservation(int(reservation_id), **updates)

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

    def _cancel_reservation(self, kwargs):
        reservation_id = kwargs.get("reservation_id")
        if not reservation_id:
            return self._missing_result(["reservation_id"])

        reservation = self.service.cancel_reservation(int(reservation_id))

        return ToolResult(
            success=True,
            message=f"Reservation {reservation.id} has been cancelled.",
            data={"reservation_id": reservation.id, "status": reservation.status},
            memory_updates={"reservation_id": None},
        )

    def _list_reservations(self, kwargs):
        reservations = self.service.list_by_status("confirmed")
        if name := kwargs.get("customer_name"):
            reservations = [r for r in reservations if name.lower() in r.customer_name.lower()]

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
            data={"reservations": [r.to_dict() for r in reservations]},
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
