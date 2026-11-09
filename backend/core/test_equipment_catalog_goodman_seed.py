"""Goodman starter catalog source and isolated import transaction tests."""

from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import TestCase

from .equipment_catalog_goodman_seed import (
    IMPORT_ROWS, REVIEW_ROWS, SOURCE_ROWS,
    import_verified_goodman_rows, row_details,
)
from .equipment_catalog_policy import validate_equipment_details
from .models import AuditEvent, AuditHead, EquipmentCatalogItem, Role, User


class GoodmanSourceInventoryTests(TestCase):
    def test_source_inventory_and_review_count(self):
        self.assertEqual(len(SOURCE_ROWS), 58)
        self.assertEqual(len(IMPORT_ROWS), 55)
        self.assertEqual(len(REVIEW_ROWS), 3)

    def test_all_source_fields_validate(self):
        for row in SOURCE_ROWS:
            with self.subTest(model=row.model_number):
                details = validate_equipment_details(row_details(row))
                self.assertEqual(details.brand, "Goodman")

    def test_source_model_families_and_review_flags(self):
        self.assertIn("AMST*13", {row.model_number for row in SOURCE_ROWS})
        self.assertEqual(
            {row.model_number for row in REVIEW_ROWS},
            {"CHPEA*3**", "GPHM5", "PHH3"},
        )


class GoodmanIsolatedImportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = User.objects.create_user(
            username="goodman_import_manager_3906",
            role=Role.SALES_MANAGER,
            initials="GIM",
        )
        cls.associate = User.objects.create_user(
            username="goodman_import_sales_3906",
            role=Role.SALES_ASSOCIATE,
            initials="GIS",
        )

    def setUp(self):
        AuditHead.objects.get_or_create(pk=1)

    def test_manager_imports_only_unflagged_rows_with_audit(self):
        result = import_verified_goodman_rows(actor_id=self.manager.pk)
        self.assertEqual(result, {
            "created": 55,
            "already_present": 0,
            "review_required": 3,
        })
        self.assertEqual(EquipmentCatalogItem.objects.count(), 55)
        self.assertEqual(
            AuditEvent.objects.filter(action="equipment.catalog.created").count(),
            55,
        )
        for row in REVIEW_ROWS:
            self.assertFalse(
                EquipmentCatalogItem.objects.filter(
                    model_number=row.model_number,
                ).exists()
            )

    def test_repeat_import_does_not_create_duplicates(self):
        import_verified_goodman_rows(actor_id=self.manager.pk)
        result = import_verified_goodman_rows(actor_id=self.manager.pk)
        self.assertEqual(result["created"], 0)
        self.assertEqual(result["already_present"], 55)
        self.assertEqual(EquipmentCatalogItem.objects.count(), 55)

    def test_unauthorized_import_rolls_back_all_rows(self):
        with self.assertRaises(PermissionDenied):
            import_verified_goodman_rows(actor_id=self.associate.pk)
        self.assertEqual(EquipmentCatalogItem.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)

    def test_failed_audit_rolls_back_entire_import(self):
        with patch(
            "core.equipment_catalog_service.audit",
            side_effect=RuntimeError("synthetic import audit failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "synthetic import audit failure"
            ):
                import_verified_goodman_rows(actor_id=self.manager.pk)
        self.assertEqual(EquipmentCatalogItem.objects.count(), 0)
        self.assertEqual(AuditEvent.objects.count(), 0)