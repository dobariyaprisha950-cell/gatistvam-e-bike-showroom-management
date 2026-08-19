from decimal import Decimal
from datetime import date, datetime, time
from uuid import UUID

from django.forms.models import model_to_dict

from .sync_models import SyncOutbox


def queue_sync(
    *,
    branch,
    instance,
    model_name=None,
    operation="CREATE",
    payload=None,
):
    """
    Add a local business record to the synchronization outbox.

    IMPORTANT:
    This function NEVER sends anything over the internet.
    It only stores a local queue record.
    """

    if branch is None:
        return None

    if not model_name:
        model_name = instance.__class__.__name__

    if payload is None:
        payload = _serialize_instance(instance)

    payload = _make_json_safe(payload)

    return SyncOutbox.objects.create(
        branch=branch,
        model_name=model_name,
        record_id=instance.pk,
        operation=operation,
        payload=payload,
    )


def _serialize_instance(instance):
    """
    Convert a Django model instance into a JSON-safe dictionary.

    ForeignKey fields are stored as their primary-key values.
    """

    cleaned = {}

    for field in instance._meta.fields:

        field_name = field.name

        try:
            value = getattr(instance, field_name)
        except AttributeError:
            continue

        # -----------------------------------------------------
        # ForeignKey
        # -----------------------------------------------------
        if field.is_relation and field.many_to_one:
            cleaned[field_name] = (
                value.pk if value is not None else None
            )
            continue

        # -----------------------------------------------------
        # Decimal
        # -----------------------------------------------------
        if isinstance(value, Decimal):
            cleaned[field_name] = str(value)
            continue

        # -----------------------------------------------------
        # Date / DateTime / Time
        # -----------------------------------------------------
        if isinstance(value, (datetime, date, time)):
            cleaned[field_name] = value.isoformat()
            continue

        # -----------------------------------------------------
        # UUID
        # -----------------------------------------------------
        if isinstance(value, UUID):
            cleaned[field_name] = str(value)
            continue

        # -----------------------------------------------------
        # File / Image
        # -----------------------------------------------------
        if hasattr(value, "name"):
            cleaned[field_name] = value.name
            continue

        # -----------------------------------------------------
        # Normal value
        # -----------------------------------------------------
        cleaned[field_name] = value

    return _make_json_safe(cleaned)

def _make_json_safe(value):
    """
    Recursively convert values into JSON-safe values.

    Handles:
    - Decimal
    - datetime
    - date
    - time
    - UUID
    - Django File/Image fields
    - dict
    - list
    - tuple
    """

    # Decimal / money
    if isinstance(value, Decimal):
        return str(value)

    # DateTime / Date / Time
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()

    # UUID
    if isinstance(value, UUID):
        return str(value)

    # Django FileField / ImageField
    if hasattr(value, "name"):
        return value.name

    # Dictionary
    if isinstance(value, dict):
        return {
            str(key): _make_json_safe(item)
            for key, item in value.items()
        }

    # List / Tuple
    if isinstance(value, (list, tuple)):
        return [
            _make_json_safe(item)
            for item in value
        ]

    # Normal JSON-safe values
    return value