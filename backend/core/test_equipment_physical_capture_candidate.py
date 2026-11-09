"""Isolated structural tests; no operational evidence creation."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest import TestCase

from .equipment_physical_capture_candidate import (
    assess_physical_capture_candidate,
)


class PhysicalCaptureCandidateTests(TestCase):
    def setUp(self):
        self.start = datetime(2026, 11, 2, 18, 0, tzinfo=timezone.utc)
        self.values = {
            "msr_id": str(uuid4()),
            "unit_id": "ROW-001-UNIT-001",
            "expected_unit_ids": ("ROW-001-UNIT-001",),
            "serial_number": " goodman-123 ",
            "recorder_id": str(uuid4()),
            "recorder_role": "INSTALLATION_MANAGER",
            "recorder_active": True,
            "captured_at": self.start - timedelta(minutes=10),
            "installation_starts_at": self.start,
        }

    def assess(self, **changes):
        return assess_physical_capture_candidate(
            **(self.values | changes)
        )

    def test_complete_candidate_still_untrusted(self):
        result = self.assess()
        self.assertTrue(result.candidate_valid, result.blockers)
        self.assertEqual(result.normalized_serial, "GOODMAN-123")
        self.assertFalse(result.physical_verification_trusted)
        self.assertFalse(result.installation_authorized)

    def test_wrong_unit_denied(self):
        result = self.assess(unit_id="ROW-999-UNIT-001")
        self.assertFalse(result.candidate_valid)
        self.assertFalse(result.installation_authorized)

    def test_wrong_recorder_role_denied(self):
        result = self.assess(recorder_role="SALES_ASSOCIATE")
        self.assertFalse(result.candidate_valid)

    def test_inactive_recorder_denied(self):
        result = self.assess(recorder_active=False)
        self.assertFalse(result.candidate_valid)

    def test_late_capture_denied(self):
        result = self.assess(
            captured_at=self.start + timedelta(seconds=1)
        )
        self.assertFalse(result.candidate_valid)

    def test_invalid_serial_denied(self):
        result = self.assess(serial_number="   ")
        self.assertFalse(result.candidate_valid)

    def test_naive_capture_time_rejected(self):
        with self.assertRaises(ValueError):
            self.assess(captured_at=self.start.replace(tzinfo=None))