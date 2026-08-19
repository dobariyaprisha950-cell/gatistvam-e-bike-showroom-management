from django.core.management.base import BaseCommand

from yakuza.sync_client import sync_pending_records


class Command(BaseCommand):
    help = "Sync pending local records to the central server."

    def handle(self, *args, **options):
        try:
            result = sync_pending_records()

            if result.get("success"):
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Sync completed | "
                        f"Synced: {result.get('synced', 0)} | "
                        f"Failed: {result.get('failed', 0)} | "
                        f"Pending: {result.get('pending', 0)}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(
                        f"Sync not completed | "
                        f"{result.get('message', 'Unknown error')} | "
                        f"Pending: {result.get('pending', 0)}"
                    )
                )

        except Exception as exc:
            self.stdout.write(
                self.style.ERROR(
                    f"Sync command failed: {exc}"
                )
            )