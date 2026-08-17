from django.core.management.base import BaseCommand

from yakuza.models import Branch
from yakuza.utils import create_daily_sales_reminder


class Command(BaseCommand):
    help = "Generates daily 7:45 PM business summary reminders per branch."

    def handle(self, *args, **options):
        active_branches = Branch.objects.filter(is_active=True)
        if not active_branches.exists():
            self.stdout.write(self.style.WARNING("No active branches found."))
            return

        for branch in active_branches:
            _, created = create_daily_sales_reminder(branch)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Generated 7:45 PM reminder for branch '{branch.branch_name}'."))
            else:
                self.stdout.write(self.style.WARNING(f"Daily reminder already exists for branch '{branch.branch_name}', or it is inactive."))
