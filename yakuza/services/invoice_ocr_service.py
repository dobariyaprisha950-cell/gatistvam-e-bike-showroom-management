"""
Production invoice OCR via Mindee Invoice API (structured fields + line items).

Why Mindee (not generic OCR like EasyOCR):
- Invoices need structured extraction (supplier, dates, line items, unit prices).
- Mindee's Invoice model returns typed fields with optional confidence scores.
- Generic OCR only yields text; regex guessing on that text is error-prone and
  violates low-confidence / no-guess requirements for purchase data.
"""
from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

from django.conf import settings

from yakuza.models import BatteryCapacity, Supplier, VehicleColor, VehicleCompany, VehicleModel
from yakuza.services.invoice_matching import match_catalog_from_description, match_supplier

logger = logging.getLogger(__name__)

# Mindee confidence when Automation is enabled; if null, value presence is used.
FIELD_CONFIDENCE_MIN = getattr(settings, 'MINDEE_FIELD_CONFIDENCE_MIN', 0.70)
LINE_ITEM_CONFIDENCE_MIN = getattr(settings, 'MINDEE_LINE_ITEM_CONFIDENCE_MIN', 0.55)


class InvoiceOcrConfigurationError(Exception):
    pass


class InvoiceOcrProcessingError(Exception):
    pass


@dataclass
class ParsedLineItem:
    company_id: Optional[int] = None
    company_name: str = ''
    model_id: Optional[int] = None
    model_name: str = ''
    color_id: Optional[int] = None
    color_name: str = ''
    battery_capacity_id: Optional[int] = None
    battery_capacity_name: str = ''
    quantity: Optional[int] = None
    unit_price: Optional[float] = None


@dataclass
class ParsedInvoice:
    invoice_number: str = ''
    invoice_date: str = ''
    supplier_id: Optional[int] = None
    supplier_name: str = ''
    items: list[ParsedLineItem] = field(default_factory=list)
    low_confidence: bool = False
    warnings: list[str] = field(default_factory=list)


def _mindee_api_key() -> str:
    key = getattr(settings, 'MINDEE_API_KEY', None) or getattr(settings, 'MINDEE_V2_API_KEY', None)
    if key:
        return key
    raise InvoiceOcrConfigurationError(
        'Mindee API key is not configured. Set MINDEE_API_KEY in the environment or Django settings.'
    )


def _field_accepted(field: Any, min_confidence: float = FIELD_CONFIDENCE_MIN) -> tuple[Any, bool]:
    if field is None:
        return None, False
    value = getattr(field, 'value', None)
    if value is None or value == '':
        return None, False
    confidence = getattr(field, 'confidence', None)
    if confidence is not None and confidence < min_confidence:
        return None, False
    return value, True


def _parse_date_value(raw: Any) -> str:
    if raw is None:
        return ''
    if isinstance(raw, datetime.date):
        return raw.isoformat()
    if isinstance(raw, datetime.datetime):
        return raw.date().isoformat()
    if isinstance(raw, str):
        text = raw.strip()
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y'):
            try:
                return datetime.datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                continue
    return ''


def _to_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        qty = int(float(value))
        return qty if qty > 0 else None
    except (TypeError, ValueError):
        return None


def _to_price(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        amount = Decimal(str(value))
        if amount <= 0:
            return None
        return float(amount.quantize(Decimal('0.01')))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _extract_with_mindee_v1(file_bytes: bytes, filename: str) -> Any:
    from mindee import Client
    from mindee import product

    client = Client(api_key=_mindee_api_key())
    input_doc = client.source_from_bytes(file_bytes, filename)
    result = client.parse(product.InvoiceV4, input_doc)
    return result.document.inference.prediction


def _line_item_description(line_item: Any) -> tuple[str, bool]:
    desc_field = getattr(line_item, 'description', None)
    if desc_field is not None:
        val, ok = _field_accepted(desc_field, FIELD_CONFIDENCE_MIN)
        if ok and val:
            return str(val).strip(), True

    product_code = getattr(line_item, 'product_code', None)
    if product_code is not None:
        val, ok = _field_accepted(product_code, FIELD_CONFIDENCE_MIN)
        if ok and val:
            return str(val).strip(), True

    return '', False


def _line_item_quantity(line_item: Any) -> Optional[int]:
    qty_field = getattr(line_item, 'quantity', None)
    val, ok = _field_accepted(qty_field, FIELD_CONFIDENCE_MIN)
    if not ok:
        return None
    return _to_int(val)


def _line_item_unit_price(line_item: Any) -> Optional[float]:
    price_field = getattr(line_item, 'unit_price', None)
    val, ok = _field_accepted(price_field, FIELD_CONFIDENCE_MIN)
    if ok:
        parsed = _to_price(val)
        if parsed is not None:
            return parsed

    total_field = getattr(line_item, 'total_price', None)
    total_val, total_ok = _field_accepted(total_field, FIELD_CONFIDENCE_MIN)
    qty = _line_item_quantity(line_item)
    if total_ok and qty:
        parsed_total = _to_price(total_val)
        if parsed_total is not None:
            return float(Decimal(str(parsed_total / qty)).quantize(Decimal('0.01')))
    return None


def _line_item_confidence_ok(line_item: Any) -> bool:
    confidence = getattr(line_item, 'confidence', None)
    if confidence is None:
        return True
    return confidence >= LINE_ITEM_CONFIDENCE_MIN


def parse_invoice_bytes(file_bytes: bytes, filename: str) -> ParsedInvoice:
    if not file_bytes:
        raise InvoiceOcrProcessingError('Uploaded file is empty.')

    allowed_ext = ('.jpg', '.jpeg', '.png', '.pdf', '.webp')
    lower_name = (filename or '').lower()
    if not any(lower_name.endswith(ext) for ext in allowed_ext):
        raise InvoiceOcrProcessingError('Unsupported file type. Use JPG, PNG, or PDF.')

    try:
        prediction = _extract_with_mindee_v1(file_bytes, filename or 'invoice.jpg')
    except InvoiceOcrConfigurationError:
        raise
    except Exception as exc:
        logger.exception('Mindee invoice parsing failed')
        raise InvoiceOcrProcessingError(f'Invoice OCR failed: {exc}') from exc

    parsed = ParsedInvoice()
    low_flags = 0

    inv_no, inv_ok = _field_accepted(getattr(prediction, 'invoice_number', None))
    if inv_ok:
        parsed.invoice_number = str(inv_no).strip()
    else:
        low_flags += 1

    inv_date_raw, date_ok = _field_accepted(getattr(prediction, 'invoice_date', None))
    if date_ok:
        parsed.invoice_date = _parse_date_value(inv_date_raw)
    else:
        low_flags += 1

    supplier_raw, supplier_ok = _field_accepted(getattr(prediction, 'supplier_name', None))
    if supplier_ok:
        supplier = match_supplier(str(supplier_raw))
        if supplier:
            parsed.supplier_id = supplier.id
            parsed.supplier_name = supplier.supplier_name
        else:
            parsed.warnings.append('Supplier read from invoice but no unique match in database.')
            low_flags += 1
    else:
        low_flags += 1

    companies = list(VehicleCompany.objects.filter(is_active=True))
    models = list(
        VehicleModel.objects.filter(is_active=True).select_related('company', 'battery_capacity')
    )
    colors = list(VehicleColor.objects.filter(is_active=True))
    batteries = list(BatteryCapacity.objects.filter(is_active=True))

    line_items = getattr(prediction, 'line_items', None) or []
    for line_item in line_items:
        if not _line_item_confidence_ok(line_item):
            low_flags += 1
            continue

        description, has_description = _line_item_description(line_item)
        quantity = _line_item_quantity(line_item)
        unit_price = _line_item_unit_price(line_item)

        if not has_description and quantity is None and unit_price is None:
            continue

        catalog = match_catalog_from_description(
            description, companies, models, colors, batteries
        ) if has_description else match_catalog_from_description('', companies, models, colors, batteries)

        item = ParsedLineItem(
            company_id=catalog.company.id if catalog.company else None,
            company_name=catalog.company.company_name if catalog.company else '',
            model_id=catalog.model.id if catalog.model else None,
            model_name=catalog.model.model_name if catalog.model else '',
            color_id=catalog.color.id if catalog.color else None,
            color_name=catalog.color.color_name if catalog.color else '',
            battery_capacity_id=catalog.battery.id if catalog.battery else None,
            battery_capacity_name=catalog.battery.capacity_name if catalog.battery else '',
            quantity=quantity,
            unit_price=unit_price,
        )

        if has_description and not catalog.model and not catalog.company:
            parsed.warnings.append(f'Line item not matched to catalog: {description[:80]}')
            low_flags += 1

        if item.quantity is None and item.unit_price is None and not item.model_name:
            continue

        parsed.items.append(item)

    parsed.low_confidence = low_flags > 0

    return parsed


def parsed_invoice_to_dict(parsed: ParsedInvoice) -> dict:
    return {
        'invoice_number': parsed.invoice_number,
        'invoice_date': parsed.invoice_date,
        'purchase_date': parsed.invoice_date,
        'supplier_id': parsed.supplier_id,
        'supplier_name': parsed.supplier_name,
        'low_confidence': parsed.low_confidence,
        'warnings': parsed.warnings,
        'items': [
            {
                'company_id': item.company_id,
                'company_name': item.company_name,
                'model_id': item.model_id,
                'model_name': item.model_name,
                'color_id': item.color_id,
                'color_name': item.color_name,
                'battery_capacity_id': item.battery_capacity_id,
                'battery_capacity_name': item.battery_capacity_name,
                'quantity': item.quantity,
                'unit_price': item.unit_price,
            }
            for item in parsed.items
        ],
    }
