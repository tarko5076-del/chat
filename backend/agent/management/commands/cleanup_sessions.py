from django.core.management.base import BaseCommand
from django.utils import timezone

from agent.models import AgentSession, SessionMessage


class Command(BaseCommand):
    help = "Clean up old agent sessions and orphaned messages"

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-age-days",
            type=int,
            default=30,
            help="Delete sessions older than N days (default: 30)",
        )
        parser.add_argument(
            "--max-sessions-per-user",
            type=int,
            default=50,
            help="Keep only N most recent sessions per user (default: 50)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )

    def handle(self, *args, **options):
        max_age_days = options["max_age_days"]
        max_per_user = options["max_sessions_per_user"]
        dry_run = options["dry_run"]

        cutoff = timezone.now() - timezone.timedelta(days=max_age_days)

        old_sessions = AgentSession.objects.filter(updated_at__lt=cutoff)
        old_count = old_sessions.count()

        orphaned = SessionMessage.objects.filter(
            session__isnull=True,
        )
        orphan_count = orphaned.count()

        excess_count = 0
        if max_per_user > 0:
            from django.db.models import Max, Subquery, OuterRef
            user_ids = AgentSession.objects.values_list("user_id", flat=True).distinct()
            for uid in user_ids:
                keep_ids = list(
                    AgentSession.objects.filter(user_id=uid)
                    .order_by("-updated_at")
                    .values_list("id", flat=True)[:max_per_user]
                )
                excess = AgentSession.objects.filter(user_id=uid).exclude(id__in=keep_ids)
                excess_count += excess.count()
                if not dry_run:
                    excess.delete()

        total = old_count + orphan_count
        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"[DRY RUN] Would delete: {old_count} old sessions (>{max_age_days}d), "
                f"{orphan_count} orphaned messages, "
                f"{excess_count} excess sessions (>{max_per_user}/user)"
            ))
        else:
            if old_count > 0:
                old_sessions.delete()
            if orphan_count > 0:
                orphaned.delete()
            self.stdout.write(self.style.SUCCESS(
                f"Deleted: {old_count} old sessions, "
                f"{orphan_count} orphaned messages, "
                f"{excess_count} excess sessions"
            ))
