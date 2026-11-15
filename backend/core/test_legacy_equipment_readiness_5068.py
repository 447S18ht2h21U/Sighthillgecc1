from django.test import SimpleTestCase

from core.installation_evidence_integrated_preview import (
    legacy_equipment_rows_incomplete,
)
from core.equipment_physical_units import NEW_MSR_FIELDS


class LegacyEquipmentReadiness5068Tests(SimpleTestCase):

    def test_older_description_and_quantity_row_is_incomplete(self):
        snapshot = {
            "equipment": [
                {"description": "Test HVAC system", "quantity": "1"}
            ]
        }
        self.assertTrue(legacy_equipment_rows_incomplete(snapshot))

    def test_structurally_complete_catalog_row_is_not_legacy(self):
        snapshot = {
            "equipment": [
                {field: "test" for field in NEW_MSR_FIELDS}
            ]
        }
        self.assertFalse(legacy_equipment_rows_incomplete(snapshot))

    def test_missing_inventory_is_not_misclassified_as_legacy(self):
        self.assertFalse(legacy_equipment_rows_incomplete({}))
        self.assertFalse(
            legacy_equipment_rows_incomplete({"equipment": []})
        )
