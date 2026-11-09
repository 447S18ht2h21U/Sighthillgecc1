"""Audited, manager-controlled residential equipment catalog operations.

No HTTP routes and no approved-document modifications are provided here.
A revision creates a new record; existing equipment details are preserved.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from .equipment_catalog_policy import (
    equipment_snapshot,
    manager_may_manage_equipment,
    validate_equipment_details,
)
from .models import EquipmentCatalogItem, User
from .services import audit


def _authorized_manager(actor_id):
    actor = User.objects.select_for_update().filter(
        pk=actor_id, is_active=True
    ).first()
    if not manager_may_manage_equipment(actor):
        raise PermissionDenied("Equipment catalog manager authorization required.")
    return actor


@transaction.atomic
def create_equipment(*, actor_id, fields):
    actor = _authorized_manager(actor_id)
    details = validate_equipment_details(fields)
    values = equipment_snapshot(details)

    if EquipmentCatalogItem.objects.filter(
        brand=values["brand"],
        residential_system_type=values["residential_system_type"],
        model_number=values["model_number"],
    ).exists():
        raise ValidationError("This equipment identity already exists.")

    record = EquipmentCatalogItem.objects.create(
        **values, created_by=actor
    )
    audit(actor, "equipment.catalog.created", record.pk, {
        "revision": record.revision,
        "equipment": values,
    })
    return record


@transaction.atomic
def revise_equipment(*, actor_id, equipment_id, fields):
    actor = _authorized_manager(actor_id)
    details = validate_equipment_details(fields)
    values = equipment_snapshot(details)

    original = EquipmentCatalogItem.objects.select_for_update().filter(
        pk=equipment_id
    ).first()
    if original is None or not original.is_active:
        raise ValidationError("An active equipment record is required.")

    # Preserve identity; new brands or model numbers are new catalog entries.
    for field in ("brand", "residential_system_type", "model_number"):
        if values[field] != getattr(original, field):
            raise ValidationError(
                "Create a new catalog entry when equipment identity changes."
            )

    if values["description"] == original.description:
        raise ValidationError("A revision must change the description.")

    latest = EquipmentCatalogItem.objects.filter(
        brand=original.brand,
        residential_system_type=original.residential_system_type,
        model_number=original.model_number,
    ).order_by("-revision").first()
    if latest is None or latest.pk != original.pk:
        raise ValidationError("Only the latest revision can be revised.")

    original.is_active = False
    original.save(update_fields=["is_active"])

    revision = EquipmentCatalogItem.objects.create(
        **values,
        revision=original.revision + 1,
        supersedes=original,
        created_by=actor,
    )
    audit(actor, "equipment.catalog.revised", revision.pk, {
        "previous_id": str(original.pk),
        "revision": revision.revision,
        "equipment": values,
    })
    return revision


@transaction.atomic
def deactivate_equipment(*, actor_id, equipment_id, reason):
    actor = _authorized_manager(actor_id)
    if type(reason) is not str or not 10 <= len(reason.strip()) <= 1000:
        raise ValidationError("A documented deactivation reason is required.")

    record = EquipmentCatalogItem.objects.select_for_update().filter(
        pk=equipment_id
    ).first()
    if record is None or not record.is_active:
        raise ValidationError("An active equipment record is required.")

    record.is_active = False
    record.save(update_fields=["is_active"])

    audit(actor, "equipment.catalog.deactivated", record.pk, {
        "revision": record.revision,
        "reason": reason.strip(),
    })
    return record