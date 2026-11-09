"""Pure tests of the unregistered physical-unit preflight."""
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

from core.equipment_identification_preflight import (
    preview_equipment_identification,
)

MSR = "11111111-1111-4111-8111-111111111111"
START = datetime(2026, 11, 1, 18, tzinfo=timezone.utc)


class EquipmentIdentificationPreflightTests(unittest.TestCase):
    def snapshot(self, quantity=2):
        return {"equipment": [{
            "brand": "Goodman",
            "residential_system_type": "Heat Pumps (R-32)",
            "model_number": "GZV9S",
            "description": "Approved synthetic equipment",
            "quantity": quantity,
            "category_of_work": "New installation",
        }]}

    def record(self, number, serial="", exception=""):
        return {
            "msr_id": MSR,
            "unit_id": f"ROW-001-UNIT-{number:03d}",
            "serial_number": serial,
            "exception_reference": exception,
            "recorded_at": START - timedelta(hours=1),
        }

    def preview(self, records, **changes):
        values = {
            "msr_id": MSR,
            "snapshot": self.snapshot(),
            "records": records,
            "installation_starts_at": START,
        }
        values.update(changes)
        return preview_equipment_identification(**values)

    def test_two_serials_are_structurally_complete_only(self):
        result = self.preview([
            self.record(1, serial="GOODMAN-A"),
            self.record(2, serial="GOODMAN-B"),
        ])
        self.assertEqual(result.expected_units, 2)
        self.assertEqual(result.recorded_units, 2)
        self.assertTrue(result.serials_structurally_complete)
        self.assertFalse(result.exceptions_independently_verified)
        self.assertFalse(result.installation_authorized)

    def test_missing_physical_unit_blocks(self):
        result = self.preview([self.record(1, serial="GOODMAN-A")])
        self.assertFalse(result.serials_structurally_complete)
        self.assertEqual(result.recorded_units, 1)
        self.assertTrue(result.blockers)

    def test_exception_claim_never_counts_as_approval(self):
        result = self.preview([
            self.record(1, serial="GOODMAN-A"),
            self.record(2, exception="CLAIMED-COMPTROLLER-APPROVAL"),
        ])
        self.assertEqual(
            result.claimed_exception_units, ("ROW-001-UNIT-002",)
        )
        self.assertFalse(result.serials_structurally_complete)
        self.assertFalse(result.exceptions_independently_verified)
        self.assertFalse(result.installation_authorized)

    def test_duplicate_serial_blocks(self):
        result = self.preview([
            self.record(1, serial="GOODMAN-A"),
            self.record(2, serial="goodman-a"),
        ])
        self.assertFalse(result.serials_structurally_complete)

    def test_record_after_installation_start_blocks(self):
        late = self.record(1, serial="GOODMAN-A")
        late["recorded_at"] = START + timedelta(seconds=1)
        result = self.preview([
            late, self.record(2, serial="GOODMAN-B")
        ])
        self.assertFalse(result.serials_structurally_complete)

    def test_multiunit_row_expands_without_serial_invention(self):
        result = self.preview(
            [self.record(1, serial="GOODMAN-A")],
            snapshot=self.snapshot(quantity=3),
        )
        self.assertEqual(result.expected_units, 3)
        self.assertFalse(result.serials_structurally_complete)

    def test_legacy_snapshot_fails_closed(self):
        with self.assertRaises(ValueError):
            self.preview(
                [],
                snapshot={"equipment": [{
                    "description": "Historical equipment"
                }]},
            )

    def test_result_is_immutable(self):
        result = self.preview([])
        with self.assertRaises(FrozenInstanceError):
            result.installation_authorized = True


if __name__ == "__main__":
    unittest.main()