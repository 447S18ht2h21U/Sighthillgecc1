"""Reusable, audited CSV product-catalog import foundation.

No persistent import authority, API endpoint, or database migration
is granted by this module.
"""
import csv
import io

from django.core.exceptions import ValidationError
from django.db import connection, transaction

from .equipment_catalog_policy import FIELDS, validate_equipment_details
from .equipment_catalog_service import _authorized_manager
from .models import EquipmentCatalogItem, ProductCatalogCollection
from .product_catalog_collections_service_4546 import (
    create_named_catalog,
    create_catalog_product,
    _catalog,
)

MAX_BYTES = 2_000_000
MAX_ROWS = 500


def parse_catalog_csv(content):
    if type(content) is not bytes or not 0 < len(content) <= MAX_BYTES:
        raise ValidationError("CSV must contain 1 to 2,000,000 bytes.")

    try:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text, newline=""))
        headers = reader.fieldnames

        if headers is None or tuple(headers) != FIELDS:
            raise ValidationError(
                "CSV columns must be brand, residential_system_type, "
                "model_number, description, in that order."
            )

        records = []
        identities = set()

        for line_number, raw in enumerate(reader, start=2):
            if len(records) >= MAX_ROWS:
                raise ValidationError("Catalog exceeds 500 products.")

            if None in raw or any(value is None for value in raw.values()):
                raise ValidationError(
                    f"Incorrect number of columns on line {line_number}."
                )

            try:
                fields = validate_equipment_details(dict(raw)).snapshot()
            except ValueError as exc:
                raise ValidationError(
                    f"Invalid equipment on line {line_number}: {exc}"
                ) from exc

            identity = tuple(fields[field] for field in FIELDS[:3])
            if identity in identities:
                raise ValidationError(
                    f"Duplicate equipment on line {line_number}."
                )

            identities.add(identity)
            records.append(fields)

    except (UnicodeError, csv.Error) as exc:
        raise ValidationError("CSV encoding or structure is invalid.") from exc

    if not records:
        raise ValidationError("Catalog contains no equipment.")

    return records


def _check_target(*, actor_id, name, description, catalog_id):
    _authorized_manager(actor_id)

    if catalog_id is not None:
        catalog = _catalog(catalog_id)
        if name is not None or description is not None:
            raise ValidationError(
                "Existing-catalog imports must not rename the catalog."
            )
        return catalog

    if type(name) is not str or not 1 <= len(name.strip()) <= 120:
        raise ValidationError("Catalog name must contain 1 to 120 characters.")

    if type(description) is not str or len(description.strip()) > 500:
        raise ValidationError("Catalog description is invalid.")

    if any(ord(ch) < 32 or ord(ch) == 127 for ch in name + description):
        raise ValidationError("Catalog text contains control characters.")

    if ProductCatalogCollection.objects.filter(
        name__iexact=name.strip()
    ).exists():
        raise ValidationError("Catalog name already exists.")

    return None


def _check_conflicts(records):
    for fields in records:
        if EquipmentCatalogItem.objects.filter(
            brand=fields["brand"],
            residential_system_type=fields["residential_system_type"],
            model_number=fields["model_number"],
        ).exists():
            raise ValidationError(
                "Existing equipment identity requires manager review: "
                + fields["model_number"]
            )


@transaction.atomic
def preview_catalog_csv(
    *, actor_id, content, name=None, description=None, catalog_id=None
):
    """Validate without creating or changing equipment or audit history."""
    records = parse_catalog_csv(content)
    catalog = _check_target(
        actor_id=actor_id,
        name=name,
        description=description,
        catalog_id=catalog_id,
    )
    _check_conflicts(records)

    return {
        "count": len(records),
        "brands": sorted({row["brand"] for row in records}),
        "catalog_id": str(catalog.pk) if catalog is not None else None,
        "rows": records,
        "ready_for_review": True,
    }


def _require_isolated_import():
    database_name = str(connection.settings_dict.get("NAME", ""))
    if (
        connection.vendor != "sqlite"
        or database_name not in (
            ":memory:",
            "file:memorydb_default?mode=memory&cache=shared",
        )
    ):
        raise RuntimeError(
            "SAFETY STOP: Bulk catalog import is not authorized "
            "on a persistent database."
        )

    import os
    if os.environ.get("VERIDIAN_0080_TEST_INSTALL") != "ISOLATED_SQLITE_MEMORY":
        raise RuntimeError("SAFETY STOP: Missing isolated test authorization.")


@transaction.atomic
def import_catalog_csv(
    *, actor_id, content, name=None, description=None, catalog_id=None
):
    """Atomic manager-confirmed import using existing audit services."""
    _require_isolated_import()

    preview = preview_catalog_csv(
        actor_id=actor_id,
        content=content,
        name=name,
        description=description,
        catalog_id=catalog_id,
    )

    if catalog_id is None:
        catalog = create_named_catalog(
            actor_id=actor_id,
            name=name,
            description=description,
        )
    else:
        catalog = _catalog(catalog_id)

    for fields in preview["rows"]:
        create_catalog_product(
            actor_id=actor_id,
            catalog_id=catalog.pk,
            fields=fields,
        )

    return catalog, preview["count"]
