"""Focused isolated tests for consolidated non-operational readiness."""
from dataclasses import FrozenInstanceError
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.test import override_settings
from django.utils import timezone

from .installation_consolidated_preview import (
    preview_consolidated_installation,
)
from .installation_three_stage_preview import PreInstallationPreview
from .equipment_serial_capture_service import capture_synthetic_serial
from .test_equipment_serial_exception_service import (
    SerialExceptionRequestServiceTests,
)


@override_settings(DEBUG=True, ENVIRONMENT="development")
class ConsolidatedPreviewTests(SerialExceptionRequestServiceTests):
    def combined(self, **changes):
        arguments = {
            "project_id": self.project.pk,
            "installation_starts_at": timezone.now() + timedelta(hours=1),
            "now": timezone.now(),
        }
        arguments.update(changes)
        return preview_consolidated_installation(**arguments)

    def save_both_serials(self, msr):
        for number in (1, 2):
            capture_synthetic_serial(
                actor=self.installation_manager,
                project_id=self.project.pk,
                msr_id=msr.pk,
                unit_id=f"ROW-001-UNIT-{number:03d}",
                serial_number=f"GOODMAN-{number}",
            )

    def stage_one_result(self, msr, ready=True):
        return PreInstallationPreview(
            msr_id=str(msr.pk),
            requirements_satisfied=ready,
            blockers=() if ready else ("Missing Contract.",),
        )

    def test_missing_real_stage_one_remains_visible(self):
        msr = self.prepare()
        self.save_both_serials(msr)
        result = self.combined()
        self.assertFalse(result.stage_one_candidate)
        self.assertTrue(result.stage_two_candidate)
        self.assertFalse(result.combined_candidate)
        self.assertFalse(result.scheduling_authorized)
        self.assertFalse(result.installation_authorized)

    def test_two_stages_can_form_only_nonoperational_candidate(self):
        msr = self.prepare()
        self.save_both_serials(msr)
        with patch(
            "core.installation_consolidated_preview.preview_pre_installation",
            return_value=self.stage_one_result(msr),
        ):
            result = self.combined()
        self.assertTrue(result.stage_one_candidate)
        self.assertTrue(result.stage_two_candidate)
        self.assertTrue(result.combined_candidate)
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.scheduling_authorized)
        self.assertFalse(result.installation_authorized)

    def test_missing_unit_blocks_stage_two(self):
        msr = self.prepare()
        with patch(
            "core.installation_consolidated_preview.preview_pre_installation",
            return_value=self.stage_one_result(msr),
        ):
            result = self.combined()
        self.assertTrue(result.stage_one_candidate)
        self.assertFalse(result.stage_two_candidate)
        self.assertFalse(result.combined_candidate)

    def test_mismatched_stage_one_msr_fails_closed(self):
        msr = self.prepare()
        self.save_both_serials(msr)
        wrong = PreInstallationPreview(
            msr_id=str(uuid4()),
            requirements_satisfied=True,
            blockers=(),
        )
        with patch(
            "core.installation_consolidated_preview.preview_pre_installation",
            return_value=wrong,
        ):
            result = self.combined()
        self.assertFalse(result.stage_one_candidate)
        self.assertFalse(result.stage_two_candidate)
        self.assertFalse(result.combined_candidate)

    def test_revoked_exception_blocks_combined_candidate(self):
        msr = self.prepare()
        request = self.request(msr)
        decision = self.decide(request)
        self.revoke(decision)
        with patch(
            "core.installation_consolidated_preview.preview_pre_installation",
            return_value=self.stage_one_result(msr),
        ):
            result = self.combined()
        self.assertTrue(result.stage_one_candidate)
        self.assertFalse(result.stage_two_candidate)
        self.assertFalse(result.combined_candidate)

    def test_result_is_immutable_and_never_authority(self):
        msr = self.prepare()
        result = self.combined()
        self.assertFalse(result.installation_authorized)
        with self.assertRaises(FrozenInstanceError):
            result.installation_authorized = True