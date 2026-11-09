"""Pure policy tests; no Django database or live installation routes."""
from dataclasses import FrozenInstanceError
from unittest import TestCase

from core.installation_start_policy_preview import preview_installation_start


class InstallationStartPolicyPreviewTests(TestCase):
    def test_scheduled_is_not_started(self):
        result = preview_installation_start(
            schedule_status="SCHEDULED",
            stage_one_candidate=True,
            stage_two_candidate=True,
        )
        self.assertTrue(result.schedule_exists)
        self.assertFalse(result.installation_started)
        self.assertFalse(result.start_authorized)

    def test_missing_stage_one_blocks(self):
        result = preview_installation_start(
            schedule_status="SCHEDULED",
            stage_one_candidate=False,
            stage_two_candidate=True,
        )
        self.assertIn("Stage 1 requirements are incomplete.", result.blockers)

    def test_missing_stage_two_blocks(self):
        result = preview_installation_start(
            schedule_status="SCHEDULED",
            stage_one_candidate=True,
            stage_two_candidate=False,
        )
        self.assertIn(
            "Stage 2 equipment identification is incomplete.", result.blockers
        )

    def test_cancelled_schedule_blocks(self):
        result = preview_installation_start(
            schedule_status="CANCELLED",
            stage_one_candidate=True,
            stage_two_candidate=True,
        )
        self.assertFalse(result.schedule_exists)
        self.assertFalse(result.start_authorized)

    def test_completed_schedule_cannot_restart(self):
        result = preview_installation_start(
            schedule_status="COMPLETED",
            stage_one_candidate=True,
            stage_two_candidate=True,
        )
        self.assertFalse(result.schedule_exists)
        self.assertFalse(result.installation_started)

    def test_forged_trust_boolean_does_not_grant_authority(self):
        result = preview_installation_start(
            schedule_status="SCHEDULED",
            stage_one_candidate=True,
            stage_two_candidate=True,
            trusted_equipment_evidence=True,
        )
        self.assertFalse(result.ready_to_start)
        self.assertFalse(result.start_authorized)
        self.assertFalse(result.installation_started)

    def test_invalid_boolean_fails_closed(self):
        result = preview_installation_start(
            schedule_status="SCHEDULED",
            stage_one_candidate=1,
            stage_two_candidate=True,
        )
        self.assertFalse(result.start_authorized)
        self.assertIn(
            "Invalid installation-start assessment inputs.", result.blockers
        )

    def test_result_is_immutable(self):
        result = preview_installation_start(
            schedule_status="SCHEDULED",
            stage_one_candidate=True,
            stage_two_candidate=True,
        )
        with self.assertRaises(FrozenInstanceError):
            result.start_authorized = True
