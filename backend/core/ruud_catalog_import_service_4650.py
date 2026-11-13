"""Protected transactional Ruud catalog import.

Import is intentionally restricted to disposable SQLite memory until
the persistent catalog database activation is separately reviewed.
"""
import json
import os
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from .equipment_catalog_policy import validate_equipment_details
from .models import (
    EquipmentCatalogItem,
    ProductCatalogCollection,
    ProductCatalogMembership,
)
from .product_catalog_collections_service_4546 import (
    create_named_catalog,
    create_catalog_product,
)
from .equipment_catalog_service import _authorized_manager


SOURCE = (
    Path(settings.BASE_DIR)
    / "core"
    / "catalog_sources"
    / "ruud_2026_20261113.json"
)


def _require_isolated_database():
    name = str(connection.settings_dict.get("NAME", ""))

    if (
        connection.vendor != "sqlite"
        or name not in (
            ":memory:",
            "file:memorydb_default?mode=memory&cache=shared",
        )
        or os.environ.get("VERIDIAN_0080_TEST_INSTALL")
        != "ISOLATED_SQLITE_MEMORY"
    ):
        raise RuntimeError(
            "SAFETY STOP: Ruud import is authorized only "
            "in a disposable in-memory SQLite test database."
        )


def _manifest():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))

    if (
        data.get("catalog_name") != "Ruud Residential Systems"
        or data.get("equipment_count") != 15
        or len(data.get("records", [])) != 15
    ):
        raise ValidationError("Unexpected Ruud catalog manifest.")

    seen_ahri = set()
    seen_identity = set()

    for row in data["records"]:
        ahri = row["ahri_reference"]
        fields = row["catalog_fields"]

        if (
            type(ahri) is not str
            or len(ahri) != 9
            or not ahri.isdecimal()
            or ahri in seen_ahri
        ):
            raise ValidationError("Invalid or duplicate AHRI reference.")

        seen_ahri.add(ahri)

        validated = validate_equipment_details(fields)

        if validated.snapshot() != fields:
            raise ValidationError("Catalog fields failed validation.")

        if fields["brand"] != "Ruud":
            raise ValidationError("Unexpected equipment manufacturer.")

        if fields["model_number"] != " / ".join((
            row["outdoor_model"],
            row["coil_model"],
            row["furnace_model"],
        )):
            raise ValidationError("Incomplete component model identity.")

        for specification in (
            ahri,
            row["outdoor_model"],
            row["coil_model"],
            row["furnace_model"],
            str(row["capacity_btuh"]),
            str(row["seer2"]),
        ):
            if specification not in fields["description"]:
                raise ValidationError("Missing equipment specification.")

        identity = (
            fields["brand"],
            fields["residential_system_type"],
            fields["model_number"],
        )

        if identity in seen_identity:
            raise ValidationError("Duplicate equipment system.")

        seen_identity.add(identity)

    return data


@transaction.atomic
def import_ruud_catalog(*, actor_id):
    """Return (catalog, created_count); fail closed on partial state."""
    _require_isolated_database()
    _authorized_manager(actor_id)

    data = _manifest()
    name = data["catalog_name"]
    records = data["records"]

    existing = ProductCatalogCollection.objects.select_for_update().filter(
        name__iexact=name
    ).first()

    if existing is not None:
        if not existing.is_active:
            raise ValidationError("Ruud catalog is inactive.")

        memberships = list(
            ProductCatalogMembership.objects.filter(
                catalog=existing
            ).select_related("equipment")
        )

        expected = {
            (
                row["catalog_fields"]["brand"],
                row["catalog_fields"]["residential_system_type"],
                row["catalog_fields"]["model_number"],
                row["catalog_fields"]["description"],
            )
            for row in records
        }

        actual = {
            (
                m.equipment.brand,
                m.equipment.residential_system_type,
                m.equipment.model_number,
                m.equipment.description,
            )
            for m in memberships
            if m.equipment.is_active
        }

        if (
            existing.description != data["catalog_description"]
            or len(memberships) != 15
            or actual != expected
            or len(actual) != 15
        ):
            raise ValidationError(
                "Existing Ruud catalog differs; "
                "manual reviewed reconciliation required."
            )

        return existing, 0

    # Reject conflicting standalone or other-catalog Ruud entries.
    for row in records:
        fields = row["catalog_fields"]

        if EquipmentCatalogItem.objects.filter(
            brand=fields["brand"],
            residential_system_type=fields["residential_system_type"],
            model_number=fields["model_number"],
        ).exists():
            raise ValidationError(
                "Existing Ruud equipment requires reviewed reconciliation."
            )

    catalog = create_named_catalog(
        actor_id=actor_id,
        name=name,
        description=data["catalog_description"],
    )

    for row in records:
        create_catalog_product(
            actor_id=actor_id,
            catalog_id=catalog.pk,
            fields=dict(row["catalog_fields"]),
        )

    return catalog, 15
