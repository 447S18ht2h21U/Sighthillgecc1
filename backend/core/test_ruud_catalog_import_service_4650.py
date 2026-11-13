"""Isolated acceptance for complete transactional Ruud import."""
from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import (
    AuditEvent,
    AuditHead,
    EquipmentCatalogItem,
    ProductCatalogCollection,
    ProductCatalogMembership,
    Role,
    User,
)
from .ruud_catalog_import_service_4650 import import_ruud_catalog
from .product_catalog_collections_service_4546 import create_named_catalog


class RuudProtectedImporter4650Tests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="ruud_import_manager_4650",
            role=Role.SALES_MANAGER,
            initials="RIM",
        )

    def setUp(self):
        AuditHead.objects.get_or_create(pk=1)

    def test_complete_import_is_audited(self):
        catalog, count = import_ruud_catalog(
            actor_id=self.manager.pk
        )

        self.assertEqual(count, 15)
        self.assertEqual(catalog.name, "Ruud Residential Systems")
        self.assertEqual(EquipmentCatalogItem.objects.count(), 15)
        self.assertEqual(ProductCatalogMembership.objects.count(), 15)

        self.assertEqual(
            AuditEvent.objects.filter(
                action="equipment.catalog.created"
            ).count(),
            15,
        )

    def test_repeat_import_does_not_duplicate_records(self):
        first, count = import_ruud_catalog(actor_id=self.manager.pk)
        self.assertEqual(count, 15)

        second, count = import_ruud_catalog(actor_id=self.manager.pk)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(count, 0)
        self.assertEqual(EquipmentCatalogItem.objects.count(), 15)
        self.assertEqual(ProductCatalogMembership.objects.count(), 15)

    def test_partial_catalog_is_rejected_without_changes(self):
        create_named_catalog(
            actor_id=self.manager.pk,
            name="Ruud Residential Systems",
            description="Partial fixture",
        )

        before = AuditEvent.objects.count()

        with self.assertRaises(ValidationError):
            import_ruud_catalog(actor_id=self.manager.pk)

        self.assertEqual(
            ProductCatalogCollection.objects.count(), 1
        )
        self.assertEqual(EquipmentCatalogItem.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_unauthorized_role_is_denied(self):
        associate = User.objects.create_user(
            username="ruud_import_associate_4650",
            role=Role.SALES_ASSOCIATE,
            initials="RIA",
        )

        from django.core.exceptions import PermissionDenied

        with self.assertRaises(PermissionDenied):
            import_ruud_catalog(actor_id=associate.pk)

        self.assertEqual(EquipmentCatalogItem.objects.count(), 0)
