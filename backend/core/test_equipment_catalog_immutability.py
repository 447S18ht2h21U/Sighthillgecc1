"""Model-level historical equipment protection tests."""

from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import EquipmentCatalogItem, Role, User


class EquipmentCatalogImmutabilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="equipment_history_manager_3904",
            role=Role.SALES_MANAGER,
            initials="EHM",
        )

    def item(self):
        return EquipmentCatalogItem.objects.create(
            brand="Goodman",
            residential_system_type="Heat Pumps (R-32)",
            model_number="GZV9S",
            description="Up to 21.0 SEER2 | Up to 10.0 HSPF2",
            created_by=self.manager,
        )

    def test_description_cannot_be_overwritten(self):
        record = self.item()
        record.description = "Unauthorized rewrite"
        with self.assertRaises(ValidationError):
            record.save()
        record.refresh_from_db()
        self.assertEqual(
            record.description,
            "Up to 21.0 SEER2 | Up to 10.0 HSPF2",
        )

    def test_equipment_identity_cannot_be_replaced(self):
        record = self.item()
        record.model_number = "FORGED"
        with self.assertRaises(ValidationError):
            record.save()
        record.refresh_from_db()
        self.assertEqual(record.model_number, "GZV9S")

    def test_catalog_record_cannot_be_deleted(self):
        record = self.item()
        with self.assertRaises(ValidationError):
            record.delete()
        self.assertTrue(
            EquipmentCatalogItem.objects.filter(pk=record.pk).exists()
        )

    def test_inactive_record_cannot_be_reactivated_directly(self):
        record = self.item()
        record.is_active = False
        record.save(update_fields=["is_active"])
        record.is_active = True
        with self.assertRaises(ValidationError):
            record.save(update_fields=["is_active"])
        record.refresh_from_db()
        self.assertFalse(record.is_active)

    def test_authorized_deactivation_preserves_details(self):
        record = self.item()
        record.is_active = False
        record.save(update_fields=["is_active"])
        record.refresh_from_db()
        self.assertFalse(record.is_active)
        self.assertEqual(record.model_number, "GZV9S")