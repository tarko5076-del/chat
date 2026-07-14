import time

from django.conf import settings
from django.utils import timezone

from reservations.models import Reservation

PERIODIC_CLEANUP_INTERVAL = getattr(settings, "RESERVATION_CLEANUP_INTERVAL", 300)

_last_cleanup: float = 0.0


def periodic_hold_cleanup() -> None:
    global _last_cleanup
    now = time.monotonic()
    if now - _last_cleanup < PERIODIC_CLEANUP_INTERVAL:
        return
    _last_cleanup = now
    try:
        expired = Reservation.objects.filter(
            status="held",
            held_until__lte=timezone.now(),
        )
        count = expired.update(status="cancelled")
        if count:
            from django.core.management import call_command
            import logging
            logging.getLogger("reservations").info(
                "Periodic cleanup released %d expired hold(s)", count
            )
    except Exception:
        pass
