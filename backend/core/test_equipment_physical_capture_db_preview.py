"""Mocked source-binding tests; operational DB integration remains separate."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from .equipment_physical_capture_db_preview import (
    preview_current_msr_physical_capture,
)


class CurrentMSRPhysicalCapturePreviewTests(TestCase):
    def setUp(self):
        self.project_id = str(uuid4())
        self.msr_id = str(uuid4())
        self.start = datetime(2026, 11, 2, 18, 0, tzinfo=timezone.utc)
        self.msr = SimpleNamespace(
            pk=self.msr_id,
            project_id=self.project_id,
            status="APPROVED",
            snapshot={"equipment": "fixture"},
        )
        self.project = SimpleNamespace(
            state="ACTIVE",
            current_approved=self.msr,
        )
        self.values = {
            "project_id": self.project_id,
            "msr_id": self.msr_id,
            "unit_id": "ROW-001-UNIT-001",
            "serial_number": "GOODMAN-123",
            "recorder_id": str(uuid4()),
            "recorder_role": "INSTALLATION_MANAGER",
            "recorder_active": True,
            "captured_at": self.start - timedelta(minutes=5),
            "installation_starts_at": self.start,
        }

    def assess(self, project, units=None, **changes):
        with patch(
            "core.equipment_physical_capture_db_preview.Project"
        ) as model, patch(
            "core.equipment_physical_capture_db_preview.physical_units_from_snapshot"
        ) as physical:
            model.objects.select_related.return_value.filter.return_value.first.return_value = project
            physical.return_value = (
                SimpleNamespace(unit_id="ROW-001-UNIT-001"),
            ) if units is None else units
            result = preview_current_msr_physical_capture(
                **(self.values | changes)
            )
            return result, physical.called

    def test_matching_msr_remains_untrusted(self):
        result, used = self.assess(self.project)
        self.assertTrue(used)
        self.assertTrue(result.candidate_valid, result.blockers)
        self.assertFalse(result.physical_verification_trusted)
        self.assertFalse(result.installation_authorized)

    def test_missing_project_fails_closed(self):
        result, used = self.assess(None)
        self.assertFalse(used)
        self.assertFalse(result.candidate_valid)

    def test_revised_msr_fails_closed(self):
        result, used = self.assess(
            self.project, msr_id=str(uuid4())
        )
        self.assertFalse(used)
        self.assertFalse(result.candidate_valid)

    def test_cancelled_project_fails_closed(self):
        self.project.state = "CANCELLED"
        result, used = self.assess(self.project)
        self.assertFalse(used)
        self.assertFalse(result.candidate_valid)

    def test_unknown_physical_unit_fails_closed(self):
        result, used = self.assess(
            self.project, unit_id="ROW-999-UNIT-001"
        )
        self.assertTrue(used)
        self.assertFalse(result.candidate_valid)
        self.assertFalse(result.installation_authorized)