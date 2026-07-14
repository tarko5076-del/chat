from django.core.management.base import BaseCommand
from django.utils import timezone

from reservations.models import Reservation


class Command(BaseCommand):
    help = "Release expired held reservations (TTL expired)"

    def handle(self, *args, **options):
        now = timezone.now()
        expired = Reservation.objects.filter(
            status="held",
            held_until__lte=now,
        )
        count = expired.update(status="cancelled")
        self.stdout.write(
            self.style.SUCCESS(f"Released {count} expired held reservations")
        )