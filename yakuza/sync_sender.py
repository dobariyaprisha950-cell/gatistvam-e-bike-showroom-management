import logging

import requests

from django.db import transaction
from django.utils import timezone

from .sync_models import SyncOutbox

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# CENTRAL SYNC API
# ---------------------------------------------------------

SYNC_API_URL = "http://127.0.0.1:8000/api/sync/receive/"


def sync_one_record(sync_record, token):
    """
    Send one PENDING SyncOutbox record to the central server.

    Returns:
        True  -> successfully synced
        False -> failed
    """

    payload = {
        "sync_id": str(sync_record.sync_id),
        "branch_code": sync_record.branch.branch_code,
        "model_name": sync_record.model_name,
        "record_id": sync_record.record_id,
        "operation": sync_record.operation,
        "payload": sync_record.payload,
    }

    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            SYNC_API_URL,
            json=payload,
            headers=headers,
            timeout=15,
        )

        sync_record.attempts += 1
        sync_record.last_attempt_at = timezone.now()

        if response.status_code in (200, 201):

            sync_record.status = "SYNCED"
            sync_record.last_error = None
            sync_record.synced_at = timezone.now()

            sync_record.save(
                update_fields=[
                    "status",
                    "attempts",
                    "last_attempt_at",
                    "last_error",
                    "synced_at",
                    "updated_at",
                ]
            )

            return True

        error_message = (
            f"HTTP {response.status_code}: "
            f"{response.text[:1000]}"
        )

        sync_record.status = "FAILED"
        sync_record.last_error = error_message

        sync_record.save(
            update_fields=[
                "status",
                "attempts",
                "last_attempt_at",
                "last_error",
                "updated_at",
            ]
        )

        return False

    except requests.RequestException as exc:

        sync_record.attempts += 1
        sync_record.last_attempt_at = timezone.now()
        sync_record.status = "FAILED"
        sync_record.last_error = str(exc)

        sync_record.save(
            update_fields=[
                "status",
                "attempts",
                "last_attempt_at",
                "last_error",
                "updated_at",
            ]
        )

        logger.exception(
            "Sync failed for SyncOutbox #%s",
            sync_record.id,
        )

        return False


def sync_pending_records(token, limit=50):
    """
    Send pending SyncOutbox records.

    Records are processed in creation order.
    """

    records = (
        SyncOutbox.objects
        .filter(status="PENDING")
        .select_related("branch")
        .order_by("created_at")[:limit]
    )

    results = {
        "total": 0,
        "synced": 0,
        "failed": 0,
    }

    for sync_record in records:

        results["total"] += 1

        if sync_one_record(sync_record, token):
            results["synced"] += 1
        else:
            results["failed"] += 1

    return results