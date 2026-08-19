import logging

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .sync_ingest import ingest_sync_record
from .models import Branch
from .sync_models import SyncOutbox, SyncStatus

logger = logging.getLogger(__name__)


class SyncReceiveView(APIView):
    """
    Central Super Admin endpoint for receiving branch synchronization data.

    Security rules:
    - TokenAuthentication is mandatory.
    - Only a user explicitly marked as Super Admin may use this endpoint.
    - The branch is resolved from the authenticated service user's profile.
    - The branch_code sent by the client is NEVER trusted for authorization.
    - sync_id makes repeated delivery idempotent.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):

        # ---------------------------------------------------------
        # 1. Super Admin authorization
        # ---------------------------------------------------------
        profile = getattr(request.user, "userprofile", None)

        if not profile or profile.role != "SUPER_ADMIN":
            return Response(
                {
                    "success": False,
                    "message": "Only Super Admin sync accounts are allowed.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # ---------------------------------------------------------
        # 2. Validate payload
        # ---------------------------------------------------------
        data = request.data

        required_fields = [
            "sync_id",
            "branch_code",
            "model_name",
            "record_id",
            "operation",
            "payload",
        ]

        missing_fields = [
            field for field in required_fields
            if field not in data
        ]

        if missing_fields:
            return Response(
                {
                    "success": False,
                    "message": "Required sync fields are missing.",
                    "missing_fields": missing_fields,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        sync_id = str(data.get("sync_id")).strip()
        branch_code = str(data.get("branch_code")).strip().upper()
        model_name = str(data.get("model_name")).strip()
        operation = str(data.get("operation")).strip().upper()
        record_id = data.get("record_id")
        payload = data.get("payload")

        if not sync_id:
            return Response(
                {
                    "success": False,
                    "message": "sync_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not branch_code:
            return Response(
                {
                    "success": False,
                    "message": "branch_code is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not model_name:
            return Response(
                {
                    "success": False,
                    "message": "model_name is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if operation not in {"CREATE", "UPDATE", "DELETE"}:
            return Response(
                {
                    "success": False,
                    "message": "Invalid synchronization operation.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(payload, dict):
            return Response(
                {
                    "success": False,
                    "message": "payload must be a JSON object.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # 3. Resolve branch from authenticated account
        # ---------------------------------------------------------
        authenticated_branch = profile.branch

        if not authenticated_branch:
            return Response(
                {
                    "success": False,
                    "message": "Sync account is not assigned to a branch.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # IMPORTANT:
        # Client-provided branch_code is checked against the
        # authenticated account's branch. It is NOT trusted.
        if authenticated_branch.branch_code.upper() != branch_code:
            logger.warning(
                "Rejected cross-branch sync attempt. "
                "User=%s authenticated_branch=%s claimed_branch=%s",
                request.user.username,
                authenticated_branch.branch_code,
                branch_code,
            )

            return Response(
                {
                    "success": False,
                    "message": "Branch authentication mismatch.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # ---------------------------------------------------------
        # 4. Idempotency check
        # ---------------------------------------------------------
        
        existing = SyncOutbox.objects.filter(sync_id=sync_id).first()

        if existing:

            # Already fully processed
            if existing.status == "SYNCED":
                return Response(
                    {
                        "success": True,
                        "message": "Record was already received and ingested.",
                        "sync_id": sync_id,
                        "duplicate": True,
                    },
                    status=status.HTTP_200_OK,
                )

            # Previous attempt failed.
            # Retry the ingest instead of silently ignoring it.
            if existing.status == "FAILED":
                try:
                    ingest_sync_record(existing)

                    existing.status = "SYNCED"
                    existing.last_error = None
                    existing.synced_at = timezone.now()
                    existing.last_attempt_at = timezone.now()
                    existing.attempts += 1

                    existing.save(
                        update_fields=[
                            "status",
                            "last_error",
                            "synced_at",
                            "last_attempt_at",
                            "attempts",
                            "updated_at",
                        ]
                    )

                    return Response(
                        {
                            "success": True,
                            "message": "Previously failed record was successfully ingested.",
                            "sync_id": sync_id,
                            "duplicate": True,
                            "retried": True,
                        },
                        status=status.HTTP_200_OK,
                    )

                except Exception as exc:
                    existing.status = "FAILED"
                    existing.last_error = str(exc)
                    existing.last_attempt_at = timezone.now()
                    existing.attempts += 1

                    existing.save(
                        update_fields=[
                            "status",
                            "last_error",
                            "last_attempt_at",
                            "attempts",
                            "updated_at",
                        ]
                    )

                    return Response(
                        {
                            "success": False,
                            "message": "Previously failed sync record could not be ingested.",
                            "sync_id": sync_id,
                            "error": str(exc),
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

        # ---------------------------------------------------------
        # 5. Validate branch
        # ---------------------------------------------------------
        try:
            branch = Branch.objects.get(
                branch_code=branch_code,
                is_active=True,
            )
        except Branch.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": "Active branch was not found.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # 6. Store received sync record
        #
        # This first version intentionally stores the payload in
        # the central outbox instead of directly modifying business
        # tables. A separate ingest processor will safely apply
        # Sales/Purchase/etc. after validation.
        # ---------------------------------------------------------
        try:
            with transaction.atomic():

                # -------------------------------------------------
                # Idempotency check
                # -------------------------------------------------
                existing_record = (
                    SyncOutbox.objects
                    .select_for_update()
                    .filter(sync_id=sync_id)
                    .first()
                )

                if existing_record is not None:

                    # Already successfully processed
                    if existing_record.status == SyncStatus.SYNCED:
                        return Response(
                            {
                                "success": True,
                                "message": "Sync record already processed.",
                                "sync_id": sync_id,
                                "status": "SYNCED",
                            },
                            status=status.HTTP_200_OK,
                        )

                    # Previously failed → retry ingestion
                    received_record = existing_record
                    received_record.branch = branch
                    received_record.model_name = model_name
                    received_record.record_id = int(record_id)
                    received_record.operation = operation
                    received_record.payload = payload
                    received_record.status = SyncStatus.PENDING
                    received_record.attempts += 1
                    received_record.last_attempt_at = timezone.now()

                    received_record.save(
                        update_fields=[
                            "branch",
                            "model_name",
                            "record_id",
                            "operation",
                            "payload",
                            "status",
                            "attempts",
                            "last_attempt_at",
                            "updated_at",
                        ]
                    )

                else:
                    # First time receiving this sync_id
                    received_record = SyncOutbox.objects.create(
                        sync_id=sync_id,
                        branch=branch,
                        model_name=model_name,
                        record_id=int(record_id),
                        operation=operation,
                        payload=payload,
                        status=SyncStatus.PENDING,
                        attempts=1,
                        last_attempt_at=timezone.now(),
                    )

                # -------------------------------------------------
                # Apply received record to central business DB
                # -------------------------------------------------
                ingest_sync_record(received_record)

                received_record.status = SyncStatus.SYNCED
                received_record.last_error = None
                received_record.synced_at = timezone.now()

                received_record.save(
                    update_fields=[
                        "status",
                        "last_error",
                        "synced_at",
                        "updated_at",
                    ]
                )

        except (ValueError, TypeError) as exc:
            logger.exception(
                "Sync ingest failed for %s",
                sync_id,
            )

            if "received_record" in locals():
                received_record.status = SyncStatus.FAILED
                received_record.last_error = str(exc)
                received_record.save(
                    update_fields=[
                        "status",
                        "last_error",
                        "updated_at",
                    ]
                )

            return Response(
                {
                    "success": False,
                    "message": "Previously failed sync record could not be ingested.",
                    "sync_id": sync_id,
                    "error": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except (ValueError, TypeError) as exc:
            logger.exception(
                "Sync ingest failed for %s",
                sync_id,
            )

            if "received_record" in locals():
                received_record.status = "FAILED"
                received_record.last_error = str(exc)
                received_record.save(
                    update_fields=[
                        "status",
                        "last_error",
                        "updated_at",
                    ]
                )

            return Response(
                {
                    "success": False,
                    "message": "Synchronization ingest failed.",
                    "error": str(exc),
                    "sync_id": sync_id,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception as exc:
            logger.exception(
                "Failed to receive/ingest sync record %s",
                sync_id,
            )

            if "received_record" in locals():
                received_record.status = "FAILED"
                received_record.last_error = str(exc)
                received_record.save(
                    update_fields=[
                        "status",
                        "last_error",
                        "updated_at",
                    ]
                )

            return Response(
                {
                    "success": False,
                    "message": "Unable to process synchronization record.",
                    "error": str(exc),
                    "sync_id": sync_id,
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )