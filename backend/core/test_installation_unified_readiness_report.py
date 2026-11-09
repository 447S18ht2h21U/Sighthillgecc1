"""Focused report composition tests; prior evidence tests are not repeated."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch, sentinel
from uuid import uuid4

from .installation_unified_readiness_report import (
    preview_unified_installation_readiness,
)


class UnifiedReadinessReportTests(TestCase):
    def setUp(self):
        self.project_id = str(uuid4())
        self.msr_id = str(uuid4())
        self.base = SimpleNamespace(
            stage_one_candidate=True,
            stage_two_candidate=True,
            stage_one_blockers=(),
            stage_two_blockers=(),
        )
        self.evidence = SimpleNamespace(
            project_id=self.project_id,
            msr_id=self.msr_id,
            installation_assessment=self.base,
            total_units=2,
            reviewed_candidate_units=2,
            all_units_reviewed=True,
            blockers=(),
        )

    def report(self, evidence=None, schedule_status="SCHEDULED"):
        if evidence is None:
            evidence = self.evidence
        with patch(
            "core.installation_unified_readiness_report.preview_installation_with_physical_reviews",
            return_value=evidence,
        ) as integrated, patch(
            "core.installation_unified_readiness_report.preview_installation_start",
            return_value=SimpleNamespace(
                schedule_exists=schedule_status == "SCHEDULED",
                blockers=("Operational installation-start authority is not implemented.",),
            ),
        ) as start:
            result = preview_unified_installation_readiness(
                project_id=self.project_id,
                installation_starts_at="2026-11-04T15:00:00+00:00",
                schedule_status=schedule_status,
            )
            integrated.assert_called_once()
            self.assertIs(
                start.call_args.kwargs["trusted_equipment_evidence"],
                False,
            )
            return result

    def assert_no_authority(self, report):
        self.assertFalse(report.schedule_verified)
        self.assertFalse(report.trusted_installation_evidence)
        self.assertFalse(report.ready_to_start)
        self.assertFalse(report.installation_authorized)
        self.assertFalse(report.installation_started)

    def test_all_candidates_complete_but_operational_start_denied(self):
        result = self.report()
        self.assertTrue(result.stage_one_candidate)
        self.assertTrue(result.stage_two_candidate)
        self.assertTrue(result.all_physical_units_reviewed)
        self.assertTrue(result.reviewed_candidate_complete)
        self.assertEqual(result.physical_units_required, 2)
        self.assertEqual(result.physical_units_reviewed, 2)
        self.assert_no_authority(result)

    def test_stage_one_blocker_is_visible(self):
        base = SimpleNamespace(
            stage_one_candidate=False,
            stage_two_candidate=True,
            stage_one_blockers=("Signed Contract is missing.",),
            stage_two_blockers=(),
        )
        evidence = SimpleNamespace(**{
            **vars(self.evidence),
            "installation_assessment": base,
        })
        result = self.report(evidence)
        self.assertFalse(result.reviewed_candidate_complete)
        self.assertIn(
            "Stage 1: Signed Contract is missing.",
            result.blockers,
        )
        self.assert_no_authority(result)

    def test_stage_two_blocker_is_visible(self):
        base = SimpleNamespace(
            stage_one_candidate=True,
            stage_two_candidate=False,
            stage_one_blockers=(),
            stage_two_blockers=("Serial capture is missing.",),
        )
        evidence = SimpleNamespace(**{
            **vars(self.evidence),
            "installation_assessment": base,
        })
        result = self.report(evidence)
        self.assertFalse(result.reviewed_candidate_complete)
        self.assertIn(
            "Stage 2: Serial capture is missing.",
            result.blockers,
        )
        self.assert_no_authority(result)

    def test_incomplete_physical_reviews_are_reported(self):
        evidence = SimpleNamespace(**{
            **vars(self.evidence),
            "reviewed_candidate_units": 1,
            "all_units_reviewed": False,
            "blockers": ("Unit ROW-002-UNIT-001: No review.",),
        })
        result = self.report(evidence)
        self.assertFalse(result.reviewed_candidate_complete)
        self.assertEqual(result.physical_units_reviewed, 1)
        self.assertTrue(any(
            "ROW-002-UNIT-001" in reason for reason in result.blockers
        ))
        self.assert_no_authority(result)

    def test_unverified_schedule_cannot_create_authority(self):
        result = self.report(schedule_status="SCHEDULED")
        self.assertTrue(result.schedule_candidate)
        self.assertFalse(result.schedule_verified)
        self.assertIn(
            "Schedule status is caller-supplied, not database-verified.",
            result.blockers,
        )
        self.assert_no_authority(result)

    def test_missing_msr_stays_default_deny(self):
        evidence = SimpleNamespace(
            project_id=self.project_id,
            msr_id="",
            installation_assessment=None,
            total_units=0,
            reviewed_candidate_units=0,
            all_units_reviewed=False,
            blockers=("Current approved MSR required.",),
        )
        result = self.report(evidence, schedule_status=None)
        self.assertFalse(result.stage_one_candidate)
        self.assertFalse(result.stage_two_candidate)
        self.assertFalse(result.reviewed_candidate_complete)
        self.assertIn(
            "Database-verified installation schedule is required.",
            result.blockers,
        )
        self.assert_no_authority(result)