from decimal import Decimal

from django.db import transaction

from .models import (
    Purchase,
    PurchaseItem,
    Stock,
    Supplier,
    VehicleCompany,
    VehicleModel,
    VehicleColor,
)


def _required(payload, field):
    """
    Return a required payload value.
    """

    value = payload.get(field)

    if value in (None, ""):
        raise ValueError(
            f"Required field '{field}' is missing."
        )

    return value


def _get_supplier(source_id):
    try:
        return Supplier.objects.get(
            pk=int(source_id)
        )
    except Supplier.DoesNotExist:
        raise ValueError(
            f"Supplier with id {source_id} was not found."
        )


def _get_company(source_id):
    try:
        return VehicleCompany.objects.get(
            pk=int(source_id)
        )
    except VehicleCompany.DoesNotExist:
        raise ValueError(
            f"VehicleCompany with id {source_id} was not found."
        )


def _get_model(source_id):
    try:
        return VehicleModel.objects.get(
            pk=int(source_id)
        )
    except VehicleModel.DoesNotExist:
        raise ValueError(
            f"VehicleModel with id {source_id} was not found."
        )


def _get_color(source_id):
    try:
        return VehicleColor.objects.get(
            pk=int(source_id)
        )
    except VehicleColor.DoesNotExist:
        raise ValueError(
            f"VehicleColor with id {source_id} was not found."
        )


@transaction.atomic
def ingest_purchase(sync_record):
    """
    Create the Purchase in the central business database.

    Idempotency:
    The source record id + branch combination is used so that
    the same Purchase is never created twice.
    """

    payload = sync_record.payload
    branch = sync_record.branch

    source_id = int(
        _required(payload, "id")
    )

    purchase_number = _required(
        payload,
        "purchase_number",
    )

    supplier = _get_supplier(
        _required(payload, "supplier")
    )

    existing = Purchase.objects.filter(
        id=source_id,
        branch=branch,
    ).first()

    if existing:
        return existing, False

    purchase = Purchase.objects.create(
        id=source_id,
        purchase_number=purchase_number,
        purchase_date=payload.get(
            "purchase_date"
        ),
        supplier=supplier,
        branch=branch,
        invoice_number=payload.get(
            "invoice_number",
            "",
        ),
        invoice_date=payload.get(
            "invoice_date"
        ),
        invoice_photo=payload.get(
            "invoice_photo"
        ) or None,
        remarks=payload.get(
            "remarks",
            "",
        ),
    )

    return purchase, True


@transaction.atomic
def ingest_purchase_item(sync_record):
    """
    Create PurchaseItem in the central business database.

    Idempotency:
    The source PurchaseItem id is preserved as the central
    PurchaseItem primary key.
    """

    payload = sync_record.payload

    source_id = int(
        _required(payload, "id")
    )

    purchase_id = int(
        _required(payload, "purchase")
    )

    company = _get_company(
        _required(payload, "company")
    )

    vehicle_model = _get_model(
        _required(payload, "model")
    )

    color = _get_color(
        _required(payload, "color")
    )

    try:
        purchase = Purchase.objects.get(
            pk=purchase_id,
            branch=sync_record.branch,
        )
    except Purchase.DoesNotExist:
        raise ValueError(
            f"Purchase with id {purchase_id} "
            f"was not found for branch "
            f"{sync_record.branch.branch_code}."
        )

    existing = PurchaseItem.objects.filter(
        id=source_id,
        purchase=purchase,
    ).first()

    if existing:
        return existing, False

    purchase_item = PurchaseItem.objects.create(
        id=source_id,
        purchase=purchase,
        company=company,
        model=vehicle_model,
        color=color,
        quantity=int(
            _required(payload, "quantity")
        ),
        purchase_price=Decimal(
            str(
                _required(
                    payload,
                    "purchase_price"
                )
            )
        ),
        subtotal=Decimal(
            str(
                payload.get(
                    "subtotal",
                    "0"
                )
            )
        ),
        cgst_amount=Decimal(
            str(
                payload.get(
                    "cgst_amount",
                    "0"
                )
            )
        ),
        sgst_amount=Decimal(
            str(
                payload.get(
                    "sgst_amount",
                    "0"
                )
            )
        ),
        total_amount=Decimal(
            str(
                payload.get(
                    "total_amount",
                    "0"
                )
            )
        ),
    )

    return purchase_item, True


@transaction.atomic
def ingest_stock(sync_record):
    """
    Create Stock in the central business database.

    Idempotency:
    The source Stock id is preserved as the central Stock
    primary key.
    """

    payload = sync_record.payload

    source_id = int(
        _required(payload, "id")
    )

    purchase_item_id = int(
        _required(payload, "purchase_item")
    )

    try:
        purchase_item = PurchaseItem.objects.get(
            pk=purchase_item_id,
            purchase__branch=sync_record.branch,
        )
    except PurchaseItem.DoesNotExist:
        raise ValueError(
            f"PurchaseItem with id {purchase_item_id} "
            f"was not found for branch "
            f"{sync_record.branch.branch_code}."
        )

    company = _get_company(
        _required(payload, "company")
    )

    vehicle_model = _get_model(
        _required(payload, "model")
    )

    color = _get_color(
        _required(payload, "color")
    )

    existing = Stock.objects.filter(
        id=source_id,
        branch=sync_record.branch,
    ).first()

    if existing:
        return existing, False

    stock = Stock.objects.create(
        id=source_id,
        purchase_item=purchase_item,
        branch=sync_record.branch,
        company=company,
        model=vehicle_model,
        color=color,
        purchase_price=Decimal(
            str(
                _required(
                    payload,
                    "purchase_price"
                )
            )
        ),
        selling_price=(
            Decimal(
                str(
                    payload["selling_price"]
                )
            )
            if payload.get("selling_price")
            not in (None, "")
            else None
        ),
        stock_status=payload.get(
            "stock_status",
            Stock.StockStatus.AVAILABLE,
        ),
        chassis_number=payload.get(
            "chassis_number"
        ),
        battery_number=payload.get(
            "battery_number"
        ),
        motor_number=payload.get(
            "motor_number"
        ),
        controller_number=payload.get(
            "controller_number"
        ),
    )

    return stock, True


def ingest_sync_record(sync_record):
    """
    Dispatch a received SyncOutbox record
    to the appropriate ingest processor.
    """

    if sync_record.model_name == "Purchase":
        return ingest_purchase(
            sync_record
        )

    if sync_record.model_name == "PurchaseItem":
        return ingest_purchase_item(
            sync_record
        )

    if sync_record.model_name == "Stock":
        return ingest_stock(
            sync_record
        )

    raise ValueError(
        f"Unsupported sync model: "
        f"{sync_record.model_name}"
    )