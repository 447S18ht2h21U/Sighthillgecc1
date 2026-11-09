"""Transactional manager-controlled named catalog operations.

Equipment identity and prior revisions remain immutable. Every new
equipment revision receives a new immutable catalog membership.
"""
from django.core.exceptions import ValidationError
from django.db import transaction

from .equipment_catalog_service import (
    _authorized_manager,
    create_equipment,
    revise_equipment,
    deactivate_equipment,
)
from .models import (
    ProductCatalogCollection,
    ProductCatalogMembership,
)
from .services import audit


def _catalog(catalog_id, *, must_be_active=True):
    catalog = (
        ProductCatalogCollection.objects.select_for_update()
        .filter(pk=catalog_id).first()
    )
    if catalog is None or (must_be_active and not catalog.is_active):
        raise ValidationError("An active product catalog is required.")
    return catalog


@transaction.atomic
def create_named_catalog(*, actor_id, name, description):
    actor = _authorized_manager(actor_id)

    if type(name) is not str or not 1 <= len(name.strip()) <= 120:
        raise ValidationError("Catalog name must contain 1 to 120 characters.")
    if type(description) is not str or len(description.strip()) > 500:
        raise ValidationError("Catalog description must contain at most 500 characters.")

    name = name.strip()
    description = description.strip()

    if any(ord(ch) < 32 or ord(ch) == 127 for ch in name + description):
        raise ValidationError("Catalog text contains prohibited control characters.")

    if ProductCatalogCollection.objects.filter(name__iexact=name).exists():
        raise ValidationError("A catalog with this name already exists.")

    catalog = ProductCatalogCollection.objects.create(
        name=name,
        description=description,
        created_by=actor,
    )
    audit(actor, "product.catalog.collection.created", catalog.pk, {
        "name": catalog.name,
        "description": catalog.description,
    })
    return catalog


@transaction.atomic
def create_catalog_product(*, actor_id, catalog_id, fields):
    actor = _authorized_manager(actor_id)
    catalog = _catalog(catalog_id)

    item = create_equipment(actor_id=actor.pk, fields=fields)
    ProductCatalogMembership.objects.create(
        catalog=catalog,
        equipment=item,
        created_by=actor,
    )
    audit(actor, "product.catalog.membership.created", item.pk, {
        "catalog_id": str(catalog.pk),
        "equipment_id": str(item.pk),
        "revision": item.revision,
    })
    return item


@transaction.atomic
def revise_catalog_product(*, actor_id, catalog_id, equipment_id, fields):
    actor = _authorized_manager(actor_id)
    catalog = _catalog(catalog_id)

    membership = (
        ProductCatalogMembership.objects.select_for_update()
        .filter(catalog=catalog, equipment_id=equipment_id)
        .first()
    )
    if membership is None:
        raise ValidationError("Product does not belong to this catalog.")

    item = revise_equipment(
        actor_id=actor.pk,
        equipment_id=equipment_id,
        fields=fields,
    )
    ProductCatalogMembership.objects.create(
        catalog=catalog,
        equipment=item,
        created_by=actor,
    )
    audit(actor, "product.catalog.membership.revised", item.pk, {
        "catalog_id": str(catalog.pk),
        "previous_equipment_id": str(equipment_id),
        "revision": item.revision,
    })
    return item


@transaction.atomic
def deactivate_catalog_product(*, actor_id, catalog_id, equipment_id, reason):
    actor = _authorized_manager(actor_id)
    catalog = _catalog(catalog_id)

    exists = ProductCatalogMembership.objects.filter(
        catalog=catalog,
        equipment_id=equipment_id,
    ).exists()
    if not exists:
        raise ValidationError("Product does not belong to this catalog.")

    return deactivate_equipment(
        actor_id=actor.pk,
        equipment_id=equipment_id,
        reason=reason,
    )


@transaction.atomic
def deactivate_named_catalog(*, actor_id, catalog_id, reason):
    actor = _authorized_manager(actor_id)
    catalog = _catalog(catalog_id)

    if type(reason) is not str or not 10 <= len(reason.strip()) <= 1000:
        raise ValidationError("A documented catalog deactivation reason is required.")

    catalog.is_active = False
    catalog.save(update_fields=["is_active"])
    audit(actor, "product.catalog.collection.deactivated", catalog.pk, {
        "name": catalog.name,
        "reason": reason.strip(),
    })
    return catalog
