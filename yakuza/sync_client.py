import logging
from datetime import timedelta

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .sync_models import SyncOutbox, SyncStatus


logger = logging.getLogger(__name__)


SYNC_TIMEOUT = 15
MAX_ATTEMPTS = 10


def sync_pending_records(limit=50):
    """
    Send pending local outbox records to the central server.

    This function is intentionally safe for local-first operation:
    - If internet is unavailable, local data remains untouched.
    - Failed records remain in the outbox for retry.
    - Successfully accepted records are marked SYNCED.
    """

    if getattr(settings, "IS_SUPER_ADMIN_CONSOLE", False):
        return {
            "success": False,
            "message": "Sync client does not run on the Super Admin console.",
            "synced": 0,
            "failed": 0,
            "pending": 0,
        }

    branch_code = getattr(settings, "BRANCH_CODE", "").strip().upper()

    if not branch_code:
        return {
            "success": False,
            "message": "BRANCH_CODE is not configured.",
            "synced": 0,
            "failed": 0,
            "pending": SyncOutbox.objects.filter(
                status=SyncStatus.PENDING
            ).count(),
        }

    registry = getattr(settings, "BRANCH_API_REGISTRY", {})
    branch_config = registry.get(branch_code)

    if not branch_config:
        return {
            "success": False,
            "message": f"No central API configuration found for branch {branch_code}.",
            "synced": 0,
            "failed": 0,
            "pending": SyncOutbox.objects.filter(
                status=SyncStatus.PENDING
            ).count(),
        }

    central_url = branch_config.get("url")
    token = branch_config.get("token")

    if not central_url or not token:
        return {
            "success": False,
            "message": f"Central API URL/token is missing for {branch_code}.",
            "synced": 0,
            "failed": 0,
            "pending": SyncOutbox.objects.filter(
                status=SyncStatus.PENDING
            ).count(),
        }

    pending_records = list(
        SyncOutbox.objects
        .filter(
            branch__branch_code=branch_code,
            status__in=[
                SyncStatus.PENDING,
                SyncStatus.FAILED,
            ],
            attempts__lt=MAX_ATTEMPTS,
        )
        .select_related("branch")
        .order_by("created_at")[:limit]
    )

    if not pending_records:
        return {
            "success": True,
            "message": "No records waiting for synchronization.",
            "synced": 0,
            "failed": 0,
            "pending": 0,
        }

    endpoint = f"{central_url.rstrip('/')}/api/sync/receive/"

    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    synced_count = 0
    failed_count = 0

    for outbox in pending_records:
        now = timezone.now()

        try:
            with transaction.atomic():
                outbox.attempts += 1
                outbox.last_attempt_at = now
                outbox.save(
                    update_fields=[
                        "attempts",
                        "last_attempt_at",
                        "updated_at",
                    ]
                )

            payload = {
                "sync_id": str(outbox.sync_id),
                "branch_code": outbox.branch.branch_code,
                "model_name": outbox.model_name,
                "record_id": outbox.record_id,
                "operation": outbox.operation,
                "payload": outbox.payload,
                "created_at": outbox.created_at.isoformat(),
            }

            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=SYNC_TIMEOUT,
            )

            if response.status_code in (200, 201, 202, 204):
                with transaction.atomic():
                    outbox.status = SyncStatus.SYNCED
                    outbox.synced_at = timezone.now()
                    outbox.last_error = None
                    outbox.save(
                        update_fields=[
                            "status",
                            "synced_at",
                            "last_error",
                            "updated_at",
                        ]
                    )

                synced_count += 1
                continue

            error_message = (
                f"Central server returned HTTP {response.status_code}"
            )

            try:
                response_data = response.json()

                if isinstance(response_data, dict):
                    server_message = response_data.get("message")

                    if server_message:
                        error_message = (
                            f"{error_message}: {server_message}"
                        )
            except ValueError:
                pass

            with transaction.atomic():
                outbox.status = SyncStatus.FAILED
                outbox.last_error = error_message
                outbox.save(
                    update_fields=[
                        "status",
                        "last_error",
                        "updated_at",
                    ]
                )

            failed_count += 1

        except requests.RequestException as exc:
            error_message = (
                f"Network error while syncing: {str(exc)}"
            )

            logger.warning(
                "Gatistvam sync network error for %s: %s",
                outbox.sync_id,
                exc,
            )

            outbox.status = SyncStatus.FAILED
            outbox.last_error = error_message
            outbox.save(
                update_fields=[
                    "status",
                    "last_error",
                    "updated_at",
                ]
            )

            failed_count += 1

        except Exception as exc:
            error_message = (
                f"Unexpected sync error: {str(exc)}"
            )

            logger.exception(
                "Unexpected Gatistvam sync error for %s",
                outbox.sync_id,
            )

            outbox.status = SyncStatus.FAILED
            outbox.last_error = error_message
            outbox.save(
                update_fields=[
                    "status",
                    "last_error",
                    "updated_at",
                ]
            )

            failed_count += 1

    remaining_pending = SyncOutbox.objects.filter(
        branch__branch_code=branch_code,
        status__in=[
            SyncStatus.PENDING,
            SyncStatus.FAILED,
        ],
        attempts__lt=MAX_ATTEMPTS,
    ).count()

    return {
        "success": failed_count == 0,
        "message": (
            "Synchronization completed."
            if failed_count == 0
            else "Synchronization completed with some failures."
        ),
        "synced": synced_count,
        "failed": failed_count,
        "pending": remaining_pending,
    }