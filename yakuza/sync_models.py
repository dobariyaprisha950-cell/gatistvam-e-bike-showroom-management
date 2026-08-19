import uuid

from django.db import models


class SyncStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SYNCED = "SYNCED", "Synced"
    FAILED = "FAILED", "Failed"


class SyncOutbox(models.Model):
    """
    Local-first synchronization queue.

    A branch writes business data locally first and creates an
    outbox record. The background sync process later sends this
    record to the central server.
    """

    id = models.BigAutoField(primary_key=True)

    sync_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
    )

    branch = models.ForeignKey(
        "Branch",
        on_delete=models.CASCADE,
        related_name="sync_outbox",
    )

    model_name = models.CharField(max_length=100)

    record_id = models.PositiveBigIntegerField()

    operation = models.CharField(
        max_length=20,
        choices=[
            ("CREATE", "Create"),
            ("UPDATE", "Update"),
            ("DELETE", "Delete"),
        ],
        default="CREATE",
    )

    payload = models.JSONField(default=dict)

    status = models.CharField(
        max_length=20,
        choices=SyncStatus.choices,
        default=SyncStatus.PENDING,
        db_index=True,
    )

    attempts = models.PositiveIntegerField(default=0)

    last_error = models.TextField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    last_attempt_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    synced_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(
                fields=["branch", "status", "created_at"]
            ),
            models.Index(
                fields=["model_name", "record_id"]
            ),
        ]

    def __str__(self):
        return (
            f"{self.branch.branch_code} | "
            f"{self.model_name} #{self.record_id} | "
            f"{self.status}"
        )


class BranchSyncStatus(models.Model):
    """
    Stores synchronization health for each branch.
    """

    branch = models.OneToOneField(
        "Branch",
        on_delete=models.CASCADE,
        related_name="sync_status",
    )

    is_online = models.BooleanField(default=False)

    last_successful_sync = models.DateTimeField(
        blank=True,
        null=True,
    )

    last_attempt_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    pending_count = models.PositiveIntegerField(
        default=0,
    )

    failed_count = models.PositiveIntegerField(
        default=0,
    )

    last_error = models.TextField(
        blank=True,
        null=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return (
            f"{self.branch.branch_code} - "
            f"{'Online' if self.is_online else 'Offline'}"
        )