"""
Match Mindee invoice extractions to showroom catalog rows without guessing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from yakuza.models import (
    BatteryCapacity,
    Supplier,
    VehicleColor,
    VehicleCompany,
    VehicleModel,
)


@dataclass
class CatalogMatch:
    company: Optional[VehicleCompany] = None
    model: Optional[VehicleModel] = None
    color: Optional[VehicleColor] = None
    battery: Optional[BatteryCapacity] = None


def _contains_phrase(haystack: str, needle: str) -> bool:
    if not needle or not haystack:
        return False
    pattern = r'(?<![\w/])' + re.escape(needle.lower()) + r'(?![\w/])'
    return re.search(pattern, haystack.lower()) is not None


def match_supplier(extracted_name: str) -> Optional[Supplier]:
    if not extracted_name:
        return None
    name = extracted_name.strip()
    if len(name) < 2:
        return None

    exact = Supplier.objects.filter(is_active=True, supplier_name__iexact=name).first()
    if exact:
        return exact

    contains = list(
        Supplier.objects.filter(is_active=True, supplier_name__icontains=name).order_by('supplier_name')
    )
    if len(contains) == 1:
        return contains[0]

    reverse = [
        s for s in Supplier.objects.filter(is_active=True).only('id', 'supplier_name')
        if s.supplier_name.lower() in name.lower()
    ]
    if len(reverse) == 1:
        return reverse[0]

    return None


def match_catalog_from_description(
    description: str,
    companies: list[VehicleCompany],
    models: list[VehicleModel],
    colors: list[VehicleColor],
    batteries: list[BatteryCapacity],
) -> CatalogMatch:
    result = CatalogMatch()
    if not description or not description.strip():
        return result

    desc = description.strip()
    desc_lower = desc.lower()

    sorted_models = sorted(models, key=lambda m: len(m.model_name), reverse=True)
    for mod in sorted_models:
        if _contains_phrase(desc, mod.model_name):
            result.model = mod
            result.company = mod.company
            result.battery = mod.battery_capacity
            break

    if not result.company:
        sorted_companies = sorted(companies, key=lambda c: len(c.company_name), reverse=True)
        for comp in sorted_companies:
            if _contains_phrase(desc, comp.company_name):
                result.company = comp
                break

    sorted_colors = sorted(colors, key=lambda c: len(c.color_name), reverse=True)
    for col in sorted_colors:
        if _contains_phrase(desc, col.color_name):
            result.color = col
            break

    sorted_batteries = sorted(batteries, key=lambda b: len(b.capacity_name), reverse=True)
    for bat in sorted_batteries:
        if _contains_phrase(desc, bat.capacity_name):
            result.battery = bat
            break

    if result.model and not result.battery:
        result.battery = result.model.battery_capacity

    return result
