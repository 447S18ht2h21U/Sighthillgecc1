"""Pure regression tests for untrusted equipment identification."""
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from core.equipment_identification_policy import (
    assess_equipment_identification,
)

MSR = "11111111-1111-4111-8111-111111111111"
START = datetime(2026, 11, 2, 15, tzinfo=timezone.utc)
BEFORE = START - timedelta(hours=1)


class EquipmentIdentificationTests(unittest.TestCase):
    def record(self, unit="unit-1", serial="ABC-100", exception=""):
        return {
            "msr_id": MSR,
            "unit_id": unit,
            "serial_number": serial,
            "exception_reference": exception,
            "recorded_at": BEFORE,
        }

    def assess(self, units=None, records=None, **changes):
        arguments = {
            "msr_id": MSR,
            "expected_unit_ids": ["unit-1"] if units is None else units,
            "records": [self.record()] if records is None else records,
            "installation_starts_at": START,
        }
        arguments.update(changes)
        return assess_equipment_identification(**arguments)

    def test_complete_serial_is_only_a_candidate(self):
        result = self.assess()
        self.assertTrue(result.candidate_complete)
        self.assertFalse(result.installation_authorized)

    def test_every_physical_unit_is_required(self):
        result = self.assess(units=["unit-1", "unit-2"])
        self.assertFalse(result.candidate_complete)
        self.assertIn("Some physical equipment units are not accounted for.",
                      result.blockers)

    def test_unique_serials_for_multiple_units(self):
        records = [
            self.record(),
            self.record(unit="unit-2", serial="XYZ-200"),
        ]
        result = self.assess(
            units=["unit-1", "unit-2"], records=records
        )
        self.assertTrue(result.candidate_complete)
        self.assertEqual(result.accounted_units, 2)

    def test_duplicate_serial_is_rejected(self):
        records = [
            self.record(),
            self.record(unit="unit-2", serial="abc-100"),
        ]
        self.assertFalse(self.assess(
            units=["unit-1", "unit-2"], records=records
        ).candidate_complete)

    def test_duplicate_unit_is_rejected(self):
        result = self.assess(records=[self.record(), self.record()])
        self.assertIn("Duplicate equipment unit record.", result.blockers)

    def test_wrong_msr_is_rejected(self):
        record = self.record()
        record["msr_id"] = str(uuid4())
        self.assertFalse(self.assess(records=[record]).candidate_complete)

    def test_late_record_is_rejected(self):
        record = self.record()
        record["recorded_at"] = START + timedelta(seconds=1)
        self.assertFalse(self.assess(records=[record]).candidate_complete)

    def test_claimed_exception_cannot_approve_itself(self):
        record = self.record(serial="", exception="CLAIMED-COMP-EXC")
        result = self.assess(records=[record])
        self.assertFalse(result.candidate_complete)
        self.assertFalse(result.exceptions_independently_verified)
        self.assertFalse(result.installation_authorized)

    def test_missing_and_conflicting_values_block(self):
        for serial, exception in (("", ""), ("ABC", "EXCEPTION")):
            with self.subTest(serial=serial, exception=exception):
                self.assertFalse(self.assess(records=[
                    self.record(serial=serial, exception=exception)
                ]).candidate_complete)

    def test_invalid_inputs_and_immutable_result(self):
        with self.assertRaises(ValueError):
            self.assess(installation_starts_at=START.replace(tzinfo=None))
        with self.assertRaises(ValueError):
            self.assess(units=["unit-1", "unit-1"])
        with self.assertRaises(ValueError):
            self.assess(msr_id="invalid")
        with self.assertRaises(FrozenInstanceError):
            self.assess().installation_authorized = True


if __name__ == "__main__":
    unittest.main()