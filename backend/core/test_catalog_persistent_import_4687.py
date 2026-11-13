"""Isolated acceptance for future persistent catalog import controls."""
from unittest.mock import patch

from django.test import TestCase

from .catalog_bulk_import_service_4670 import (
    import_catalog_csv,
    import_catalog_csv_persistent,
)
from .models import (
    AuditEvent,
    AuditHead,
    EquipmentCatalogItem,
    Outbox,
    ProductCatalogCollection,
    ProductCatalogMembership,
    Role,
    User,
)
from .product_catalog_collections_service_4546 import create_named_catalog

HEADER = "brand,residential_system_type,model_number,description\n"

def sample_csv():
    return (
        HEADER
        + "Carrier,Heat Pump,CA-4687-1,First fixture\n"
        + "Carrier,Furnace,CA-4687-2,Second fixture\n"
    ).encode("utf-8")


class ProtectedCatalogImport4687Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="catalog_manager_4687",
            role=Role.INSTALLATION_MANAGER,
            initials="CM",
        )

    def setUp(self):
        AuditHead.objects.get_or_create(pk=1)

    def test_persistent_entry_point_remains_locked(self):
        with self.assertRaisesRegex(
            RuntimeError, "not activated"
        ):
            import_catalog_csv_persistent(
                actor_id=self.manager.pk,
                content=sample_csv(),
                name="Carrier Rehearsal",
                description="Disposable records only",
            )

        self.assertEqual(EquipmentCatalogItem.objects.count(), 0)
        self.assertEqual(ProductCatalogCollection.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_import_second_row_failure_rolls_back_everything(self):
        from . import catalog_bulk_import_service_4670 as service
        actual_create = service.create_catalog_product
        calls = 0

        def fail_after_first(*, actor_id, catalog_id, fields):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValueError("Simulated second-row failure.")
            return actual_create(
                actor_id=actor_id,
                catalog_id=catalog_id,
                fields=fields,
            )

        with patch.object(
            service, "create_catalog_product",
            side_effect=fail_after_first,
        ):
            with self.assertRaisesRegex(
                ValueError, "Simulated second-row failure"
            ):
                import_catalog_csv(
                    actor_id=self.manager.pk,
                    content=sample_csv(),
                    name="Carrier Rehearsal",
                    description="Disposable records only",
                )

        self.assertEqual(calls, 2)
        self.assertEqual(EquipmentCatalogItem.objects.count(), 0)
        self.assertEqual(ProductCatalogCollection.objects.count(), 0)
        self.assertEqual(ProductCatalogMembership.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)
        self.assertEqual(Outbox.objects.count(), 0)

    def test_existing_catalog_import_reuses_audit_services(self):
        catalog = create_named_catalog(
            actor_id=self.manager.pk,
            name="Carrier Existing Catalog",
            description="Disposable acceptance",
        )

        imported, count = import_catalog_csv(
            actor_id=self.manager.pk,
            content=sample_csv(),
            catalog_id=catalog.pk,
        )

        self.assertEqual(imported.pk, catalog.pk)
        self.assertEqual(count, 2)
        self.assertEqual(ProductCatalogCollection.objects.count(), 1)
        self.assertEqual(EquipmentCatalogItem.objects.count(), 2)
        self.assertEqual(ProductCatalogMembership.objects.count(), 2)
        self.assertEqual(AuditEvent.objects.count(), 5)
        self.assertEqual(Outbox.objects.count(), 5)

    def test_inactive_manager_cannot_import(self):
        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])

        from django.core.exceptions import PermissionDenied

        with self.assertRaises(PermissionDenied):
            import_catalog_csv(
                actor_id=self.manager.pk,
                content=sample_csv(),
                name="Denied Catalog",
                description="Disposable acceptance",
            )

        self.assertEqual(EquipmentCatalogItem.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)
