"""Fail-closed identity checks with mocked database access."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch, sentinel
from uuid import uuid4

from .equipment_physical_capture_actor_preview import (
    preview_identified_physical_capture,
)


class PhysicalCaptureActorPreviewTests(TestCase):
    def setUp(self):
        self.values = {
            "project_id": str(uuid4()),
            "msr_id": str(uuid4()),
            "unit_id": "ROW-001-UNIT-001",
            "serial_number": "GOODMAN-123",
            "recorder_id": str(uuid4()),
            "captured_at": datetime(2026, 11, 2, 17, 0, tzinfo=timezone.utc),
            "installation_starts_at": datetime(
                2026, 11, 2, 18, 0, tzinfo=timezone.utc
            ),
        }

    def run_case(self, recorder, **changes):
        with patch(
            "core.equipment_physical_capture_actor_preview.User"
        ) as users, patch(
            "core.equipment_physical_capture_actor_preview.preview_current_msr_physical_capture"
        ) as adapter:
            users.objects.filter.return_value.first.return_value = recorder
            adapter.return_value = sentinel.candidate
            result = preview_identified_physical_capture(
                **(self.values | changes)
            )
            return result, adapter

    def test_actual_active_manager_passes_to_untrusted_adapter(self):
        user = SimpleNamespace(is_active=True, role="INSTALLATION_MANAGER")
        result, adapter = self.run_case(user)
        self.assertIs(result, sentinel.candidate)
        self.assertEqual(adapter.call_args.kwargs["recorder_role"], "INSTALLATION_MANAGER")
        self.assertIs(adapter.call_args.kwargs["recorder_active"], True)

    def test_sales_associate_is_denied(self):
        user = SimpleNamespace(is_active=True, role="SALES_ASSOCIATE")
        result, adapter = self.run_case(user)
        self.assertFalse(result.candidate_valid)
        self.assertFalse(result.installation_authorized)
        adapter.assert_not_called()

    def test_inactive_manager_is_denied(self):
        user = SimpleNamespace(is_active=False, role="INSTALLATION_MANAGER")
        result, adapter = self.run_case(user)
        self.assertFalse(result.candidate_valid)
        adapter.assert_not_called()

    def test_nonexistent_recorder_is_denied(self):
        result, adapter = self.run_case(None)
        self.assertFalse(result.candidate_valid)
        adapter.assert_not_called()

    def test_invalid_recorder_identifier_is_rejected(self):
        with self.assertRaises(ValueError):
            self.run_case(None, recorder_id="not-a-uuid")