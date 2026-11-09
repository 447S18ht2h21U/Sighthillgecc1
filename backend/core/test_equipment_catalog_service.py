"""Transaction and authorization checks for catalog manager operations."""

from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from .equipment_catalog_service import (
    create_equipment,
    deactivate_equipment,
    revise_equipment,
)
from .models import AuditEvent, AuditHead, EquipmentCatalogItem, Role, User


class EquipmentCatalogServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.sales_manager = User.objects.create_user(
            username="equipment_sales_manager_3903",
            role=Role.SALES_MANAGER,
            initials="ESM",
        )
        cls.installation_manager = User.objects.create_user(
            username="equipment_install_manager_3903",
            role=Role.INSTALLATION_MANAGER,
            initials="EIM",
        )
        cls.sales_associate = User.objects.create_user(
            username="equipment_sales_associate_3903",
            role=Role.SALES_ASSOCIATE,
            initials="ESA",
        )

    def setUp(self):
        AuditHead.objects.get_or_create(pk=1)
        self.fields = {
            "brand": "Goodman",
            "residential_system_type": "Heat Pumps (R-32)",
            "model_number": "GZV9S",
            "description": "Up to 21.0 SEER2 | Up to 10.0 HSPF2",
        }

    def create(self, actor=None):
        return create_equipment(
            actor_id=(actor or self.sales_manager).pk,
            fields=dict(self.fields),
        )

    def test_sales_manager_creates_and_audits(self):
        item = self.create()
        self.assertEqual(item.created_by_id, self.sales_manager.pk)
        self.assertEqual(item.description, self.fields["description"])
        self.assertEqual(
            AuditEvent.objects.filter(action="equipment.catalog.created").count(), 1
        )

    def test_installation_manager_can_create(self):
        item = self.create(self.installation_manager)
        self.assertTrue(item.is_active)

    def test_sales_associate_cannot_create(self):
        with self.assertRaises(PermissionDenied):
            self.create(self.sales_associate)
        self.assertEqual(EquipmentCatalogItem.objects.count(), 0)

    def test_inactive_manager_cannot_create(self):
        self.sales_manager.is_active = False
        self.sales_manager.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            self.create()

    def test_duplicate_identity_is_rejected(self):
        self.create()
        with self.assertRaises(ValidationError):
            self.create()
        self.assertEqual(EquipmentCatalogItem.objects.count(), 1)

    def test_revision_preserves_old_description(self):
        original = self.create()
        new_fields = dict(self.fields, description="Updated Goodman specification")
        revised = revise_equipment(
            actor_id=self.installation_manager.pk,
            equipment_id=original.pk,
            fields=new_fields,
        )
        original.refresh_from_db()
        self.assertFalse(original.is_active)
        self.assertEqual(original.description, self.fields["description"])
        self.assertEqual(revised.revision, 2)
        self.assertEqual(revised.supersedes_id, original.pk)
        self.assertEqual(
            AuditEvent.objects.filter(action="equipment.catalog.revised").count(), 1
        )

    def test_deactivation_retains_historical_record(self):
        item = self.create()
        deactivate_equipment(
            actor_id=self.installation_manager.pk,
            equipment_id=item.pk,
            reason="Manufacturer model has been discontinued.",
        )
        item.refresh_from_db()
        self.assertFalse(item.is_active)
        self.assertEqual(EquipmentCatalogItem.objects.count(), 1)
        self.assertEqual(
            AuditEvent.objects.filter(action="equipment.catalog.deactivated").count(), 1
        )

    def test_failed_audit_rolls_back_new_entry(self):
        with patch(
            "core.equipment_catalog_service.audit",
            side_effect=RuntimeError("synthetic equipment audit failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "synthetic equipment audit failure"):
                self.create()
        self.assertEqual(EquipmentCatalogItem.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)