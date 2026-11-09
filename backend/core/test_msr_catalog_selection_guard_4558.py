"""Isolated MSR named-catalog save-boundary regression tests."""
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from .msr_catalog_selection_guard_4558 import (
    verify_new_equipment_selections,
)

CATALOG = str(uuid4())
PRODUCT = str(uuid4())

FIELDS = {
    "brand": "TEST BRAND",
    "residential_system_type": "Heat Pump",
    "model_number": "TEST-HP-003",
    "description": "Fictional heat pump for integration testing",
}

SIX_FIELDS = {
    **FIELDS,
    "quantity": 1,
    "category_of_work": "New installation",
}


class CatalogGuard4558Tests(SimpleTestCase):
    def proposal(self, **changes):
        return {
            "equipment": [{
                **SIX_FIELDS,
                "catalog_id": CATALOG,
                "equipment_id": PRODUCT,
                **changes,
            }]
        }

    def verified(self, *, active=True):
        membership = (
            SimpleNamespace(equipment=SimpleNamespace(**FIELDS))
            if active else None
        )
        patcher = patch(
            "core.msr_catalog_selection_guard_4558."
            "ProductCatalogMembership.objects.select_related"
        )
        lookup = patcher.start()
        self.addCleanup(patcher.stop)
        lookup.return_value.filter.return_value.first.return_value = membership
        return lookup

    def test_valid_product_uses_verified_membership(self):
        lookup = self.verified()
        supplied = self.proposal()
        checked = verify_new_equipment_selections(supplied, {})
        self.assertEqual(checked["equipment"], [SIX_FIELDS])
        self.assertIn("catalog_id", supplied["equipment"][0])
        self.assertEqual(lookup.call_count, 1)
        self.assertEqual(
            lookup.return_value.filter.call_args.kwargs[
                "catalog__is_active"
            ],
            True,
        )
        self.assertEqual(
            lookup.return_value.filter.call_args.kwargs[
                "equipment__is_active"
            ],
            True,
        )

    def test_unknown_product_rejected(self):
        self.verified(active=False)
        with self.assertRaises(ValidationError):
            verify_new_equipment_selections(self.proposal(), {})

    def test_missing_product_reference_rejected(self):
        with self.assertRaises(ValidationError):
            verify_new_equipment_selections(
                {"equipment": [dict(SIX_FIELDS)]}, {}
            )

    def test_partial_reference_rejected(self):
        with self.assertRaises(ValidationError):
            verify_new_equipment_selections(
                {"equipment": [{**SIX_FIELDS, "catalog_id": CATALOG}]},
                {},
            )

    def test_invalid_uuid_rejected(self):
        with self.assertRaises(ValidationError):
            verify_new_equipment_selections(
                self.proposal(equipment_id="not-a-uuid"), {}
            )

    def test_modified_catalog_description_rejected(self):
        self.verified()
        with self.assertRaises(ValidationError):
            verify_new_equipment_selections(
                self.proposal(description="Tampered"), {}
            )

    def test_old_snapshot_preserved_without_catalog_lookup(self):
        old = {"equipment": [dict(SIX_FIELDS)]}
        with patch(
            "core.msr_catalog_selection_guard_4558."
            "ProductCatalogMembership.objects.select_related"
        ) as lookup:
            checked = verify_new_equipment_selections(old, old)
        self.assertEqual(checked, old)
        lookup.assert_not_called()

    def test_existing_quantity_change_remains_historical(self):
        old = {"equipment": [dict(SIX_FIELDS)]}
        edited = {
            "equipment": [{**SIX_FIELDS, "quantity": 2}]
        }
        with patch(
            "core.msr_catalog_selection_guard_4558."
            "ProductCatalogMembership.objects.select_related"
        ) as lookup:
            result = verify_new_equipment_selections(edited, old)
        self.assertEqual(result, edited)
        lookup.assert_not_called()

    def test_duplicate_old_line_requires_new_reference(self):
        previous = {"equipment": [dict(SIX_FIELDS)]}
        attempt = {
            "equipment": [dict(SIX_FIELDS), dict(SIX_FIELDS)]
        }
        with self.assertRaises(ValidationError):
            verify_new_equipment_selections(attempt, previous)

    def test_legacy_historical_line_survives(self):
        original = {
            "equipment": [{
                "description": "Historical equipment",
                "quantity": "1",
            }]
        }
        self.assertEqual(
            verify_new_equipment_selections(original, original),
            original,
        )
