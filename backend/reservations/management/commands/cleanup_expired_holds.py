import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from reservations.models import Reservation

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Release all expired reservation holds."

    def handle(self, *args, **options):
        now = timezone.now()
        expired = Reservation.objects.filter(
            status="held",
            held_until__lte=now,
        )
        count = expired.update(status="cancelled")
        if count:
            logger.info("Released %d expired reservation holds", count)
        self.stdout.write(f"Released {count} expired hold(s).")
