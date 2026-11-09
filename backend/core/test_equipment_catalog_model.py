"""Isolated persistence tests for the residential equipment catalog."""

from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import EquipmentCatalogItem, Role, User


class EquipmentCatalogModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="catalog_test_manager_3902b",
            role=Role.SALES_MANAGER,
            initials="ECM",
        )

    def item(self, **changes):
        details = {
            "brand": "Goodman",
            "residential_system_type": "Heat Pumps (R-32)",
            "model_number": "GZV9S",
            "description": "Up to 21.0 SEER2 | Up to 10.0 HSPF2",
            "created_by": self.manager,
        }
        details.update(changes)
        return EquipmentCatalogItem.objects.create(**details)

    def test_four_fields_persist(self):
        item = self.item()
        item.refresh_from_db()
        self.assertEqual(item.brand, "Goodman")
        self.assertEqual(item.residential_system_type, "Heat Pumps (R-32)")
        self.assertEqual(item.model_number, "GZV9S")
        self.assertEqual(item.description, "Up to 21.0 SEER2 | Up to 10.0 HSPF2")

    def test_new_entry_defaults(self):
        item = self.item()
        self.assertTrue(item.is_active)
        self.assertEqual(item.revision, 1)

    def test_duplicate_identity_and_revision_denied(self):
        self.item()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.item()

    def test_revision_retains_historical_entry(self):
        original = self.item()
        original.is_active = False
        original.save(update_fields=["is_active"])
        revised = self.item(
            revision=2,
            supersedes=original,
            description="Revised manufacturer specification",
        )
        original.refresh_from_db()
        self.assertFalse(original.is_active)
        self.assertEqual(original.description, "Up to 21.0 SEER2 | Up to 10.0 HSPF2")
        self.assertEqual(revised.supersedes_id, original.pk)

    def test_family_model_wildcard_persists(self):
        item = self.item(model_number="AMST*13")
        item.refresh_from_db()
        self.assertEqual(item.model_number, "AMST*13")

    def test_inactive_record_is_not_deleted(self):
        item = self.item()
        item.is_active = False
        item.save(update_fields=["is_active"])
        self.assertTrue(
            EquipmentCatalogItem.objects.filter(
                pk=item.pk, is_active=False
            ).exists()
        )