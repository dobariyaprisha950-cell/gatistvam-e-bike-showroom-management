import logging

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Branch
from .sync_ingest import ingest_sync_record
from .sync_models import SyncOutbox, SyncStatus


logger = logging.getLogger(__name__)


class SyncReceiveView(APIView):
    """
    Central Super Admin endpoint for receiving branch synchronization data.

    Security:
    - TokenAuthentication is mandatory.
    - Only SUPER_ADMIN accounts may use this endpoint.
    - Branch is resolved from the authenticated user's profile.
    - Client branch_code must match the authenticated branch.
    - sync_id provides idempotent delivery.
    """

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):

        # =========================================================
        # 1. SUPER ADMIN AUTHORIZATION
        # =========================================================

        profile = getattr(request.user, "userprofile", None)

        if not profile or profile.role != "SUPER_ADMIN":
            return Response(
                {
                    "success": False,
                    "message": "Only Super Admin sync accounts are allowed.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # =========================================================
        # 2. VALIDATE PAYLOAD
        # =========================================================

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
            field
            for field in required_fields
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

        try:
            record_id = int(record_id)
        except (TypeError, ValueError):
            return Response(
                {
                    "success": False,
                    "message": "record_id must be a valid integer.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # =========================================================
        # 3. RESOLVE AUTHENTICATED BRANCH
        # =========================================================

        authenticated_branch = profile.branch

        if not authenticated_branch:
            return Response(
                {
                    "success": False,
                    "message": "Sync account is not assigned to a branch.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if (
            authenticated_branch.branch_code.upper()
            != branch_code
        ):
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

        # =========================================================
        # 4. VALIDATE ACTIVE BRANCH
        # =========================================================

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

        # =========================================================
        # 5. IDEMPOTENCY CHECK
        # =========================================================

        existing = SyncOutbox.objects.filter(
            sync_id=sync_id
        ).first()

        if existing:

            # -----------------------------------------------------
            # Already successfully processed
            # -----------------------------------------------------

            if existing.status == SyncStatus.SYNCED:
                return Response(
                    {
                        "success": True,
                        "message": "Record was already received and ingested.",
                        "sync_id": sync_id,
                        "duplicate": True,
                        "status": "SYNCED",
                    },
                    status=status.HTTP_200_OK,
                )

            # -----------------------------------------------------
            # Previously failed
            # -----------------------------------------------------

            if existing.status == SyncStatus.FAILED:

                try:
                    existing.status = SyncStatus.PENDING
                    existing.attempts += 1
                    existing.last_attempt_at = timezone.now()

                    existing.save(
                        update_fields=[
                            "status",
                            "attempts",
                            "last_attempt_at",
                            "updated_at",
                        ]
                    )

                    ingest_sync_record(existing)

                    existing.status = SyncStatus.SYNCED
                    existing.last_error = None
                    existing.synced_at = timezone.now()

                    existing.save(
                        update_fields=[
                            "status",
                            "last_error",
                            "synced_at",
                            "updated_at",
                        ]
                    )

                    return Response(
                        {
                            "success": True,
                            "message": (
                                "Previously failed record "
                                "was successfully ingested."
                            ),
                            "sync_id": sync_id,
                            "duplicate": True,
                            "retried": True,
                            "status": "SYNCED",
                        },
                        status=status.HTTP_200_OK,
                    )

                except Exception as exc:

                    logger.exception(
                        "Retry ingest failed for sync_id=%s",
                        sync_id,
                    )

                    existing.status = SyncStatus.FAILED
                    existing.last_error = str(exc)
                    existing.last_attempt_at = timezone.now()

                    existing.save(
                        update_fields=[
                            "status",
                            "last_error",
                            "last_attempt_at",
                            "updated_at",
                        ]
                    )

                    return Response(
                        {
                            "success": False,
                            "message": (
                                "Previously failed sync record "
                                "could not be ingested."
                            ),
                            "sync_id": sync_id,
                            "error": str(exc),
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

        # =========================================================
        # 6. CREATE / STORE / INGEST NEW RECORD
        # =========================================================

        received_record = None

        try:
            with transaction.atomic():

                # -------------------------------------------------
                # Lock possible duplicate row
                # -------------------------------------------------

                existing_record = (
                    SyncOutbox.objects
                    .select_for_update()
                    .filter(sync_id=sync_id)
                    .first()
                )

                if existing_record:

                    # Another request may have created it
                    # between our first check and this transaction.

                    if existing_record.status == SyncStatus.SYNCED:
                        return Response(
                            {
                                "success": True,
                                "message": "Sync record already processed.",
                                "sync_id": sync_id,
                                "duplicate": True,
                                "status": "SYNCED",
                            },
                            status=status.HTTP_200_OK,
                        )

                    received_record = existing_record

                    received_record.branch = branch
                    received_record.model_name = model_name
                    received_record.record_id = record_id
                    received_record.operation = operation
                    received_record.payload = payload
                    received_record.status = SyncStatus.PENDING
                    received_record.attempts += 1
                    received_record.last_attempt_at = timezone.now()
                    received_record.last_error = None

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
                            "last_error",
                            "updated_at",
                        ]
                    )

                else:

                    # -------------------------------------------------
                    # First delivery
                    # -------------------------------------------------

                    received_record = SyncOutbox.objects.create(
                        sync_id=sync_id,
                        branch=branch,
                        model_name=model_name,
                        record_id=record_id,
                        operation=operation,
                        payload=payload,
                        status=SyncStatus.PENDING,
                        attempts=1,
                        last_attempt_at=timezone.now(),
                    )

                # -------------------------------------------------
                # INGEST INTO CENTRAL BUSINESS DATABASE
                # -------------------------------------------------

                ingest_sync_record(received_record)

                # -------------------------------------------------
                # MARK SYNCED
                # -------------------------------------------------

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

        except Exception as exc:

            logger.exception(
                "Failed to receive/ingest sync record %s",
                sync_id,
            )

            if received_record is not None:

                try:
                    received_record.status = SyncStatus.FAILED
                    received_record.last_error = str(exc)
                    received_record.last_attempt_at = timezone.now()

                    received_record.save(
                        update_fields=[
                            "status",
                            "last_error",
                            "last_attempt_at",
                            "updated_at",
                        ]
                    )

                except Exception:
                    logger.exception(
                        "Could not save FAILED status for sync_id=%s",
                        sync_id,
                    )

            return Response(
                {
                    "success": False,
                    "message": "Sync record could not be ingested.",
                    "sync_id": sync_id,
                    "error": str(exc),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # =========================================================
        # 7. SUCCESS RESPONSE
        # =========================================================

        return Response(
            {
                "success": True,
                "message": "Sync record received and ingested successfully.",
                "sync_id": sync_id,
                "branch_code": branch_code,
                "model_name": model_name,
                "record_id": record_id,
                "operation": operation,
                "status": "SYNCED",
            },
            status=status.HTTP_200_OK,
        )