"""Focused isolated acceptance for reusable manufacturer CSV imports."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from .catalog_bulk_import_service_4670 import (
    import_catalog_csv,
    preview_catalog_csv,
)
from .models import (
    AuditEvent, AuditHead, EquipmentCatalogItem,
    ProductCatalogCollection, ProductCatalogMembership,
    Role, User,
)

HEADER = "brand,residential_system_type,model_number,description\n"


class BulkCatalogImport4670Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="bulk_catalog_manager_4670",
            role=Role.SALES_MANAGER,
            initials="BM",
        )
        cls.associate = User.objects.create_user(
            username="bulk_catalog_associate_4670",
            role=Role.SALES_ASSOCIATE,
            initials="BA",
        )

    def setUp(self):
        AuditHead.objects.get_or_create(pk=1)

    def content(self):
        return (
            HEADER
            + "Goodman,Heat Pump,GM-100,Goodman sample model\n"
            + "Ruud,Air Conditioner,RD-200,Ruud sample model\n"
        ).encode("utf-8")

    def test_preview_has_no_writes(self):
        result = preview_catalog_csv(
            actor_id=self.manager.pk,
            content=self.content(),
            name="Example Manufacturer Catalog",
            description="Disposable acceptance example",
        )

        self.assertEqual(result["count"], 2)
        self.assertEqual(result["brands"], ["Goodman", "Ruud"])
        self.assertEqual(EquipmentCatalogItem.objects.count(), 0)
        self.assertEqual(ProductCatalogCollection.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_import_creates_audited_memberships(self):
        catalog, count = import_catalog_csv(
            actor_id=self.manager.pk,
            content=self.content(),
            name="Example Manufacturer Catalog",
            description="Disposable acceptance example",
        )

        self.assertEqual(count, 2)
        self.assertEqual(catalog.name, "Example Manufacturer Catalog")
        self.assertEqual(EquipmentCatalogItem.objects.count(), 2)
        self.assertEqual(ProductCatalogMembership.objects.count(), 2)
        self.assertEqual(AuditEvent.objects.count(), 5)

    def test_duplicate_file_rejected_without_writes(self):
        content = (
            HEADER
            + "Ruud,Heat Pump,RD-1,First specification\n"
            + "Ruud,Heat Pump,RD-1,Second specification\n"
        ).encode("utf-8")

        with self.assertRaises(ValidationError):
            import_catalog_csv(
                actor_id=self.manager.pk,
                content=content,
                name="Duplicate Example",
                description="Disposable example",
            )

        self.assertEqual(EquipmentCatalogItem.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_unauthorized_associate_denied(self):
        with self.assertRaises(PermissionDenied):
            import_catalog_csv(
                actor_id=self.associate.pk,
                content=self.content(),
                name="Unauthorized Example",
                description="Disposable example",
            )

        self.assertEqual(ProductCatalogCollection.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_invalid_row_does_not_create_partial_catalog(self):
        content = (
            HEADER
            + "Ruud,Heat Pump,RD-1,Valid product\n"
            + "Ruud,Heat Pump,,Missing model\n"
        ).encode("utf-8")

        with self.assertRaises(ValidationError):
            import_catalog_csv(
                actor_id=self.manager.pk,
                content=content,
                name="Invalid Example",
                description="Disposable example",
            )

        self.assertEqual(EquipmentCatalogItem.objects.count(), 0)
        self.assertEqual(ProductCatalogCollection.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)
