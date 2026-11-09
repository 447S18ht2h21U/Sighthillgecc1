"""Focused security tests for combined installation evidence preview."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch, sentinel
from uuid import uuid4

from .installation_evidence_integrated_preview import (
    preview_installation_with_physical_reviews,
)


class IntegratedReadinessTests(TestCase):
    def setUp(self):
        self.project_id = str(uuid4())
        self.msr_id = str(uuid4())
        self.project = SimpleNamespace(
            state="ACTIVE",
            current_approved=SimpleNamespace(
                pk=self.msr_id,
                project_id=self.project_id,
                status="APPROVED",
                snapshot={"equipment": []},
            ),
        )
        self.unit_ids = ("ROW-001-UNIT-001", "ROW-002-UNIT-001")

    def assess(self, *, project=None, units=None, verified=None):
        if project is None:
            project = self.project
        if units is None:
            units = self.unit_ids
        if verified is None:
            verified = set(units)
        with patch(
            "core.installation_evidence_integrated_preview.Project"
        ) as projects, patch(
            "core.installation_evidence_integrated_preview.physical_units_from_snapshot"
        ) as inventory, patch(
            "core.installation_evidence_integrated_preview.preview_consolidated_installation"
        ) as base, patch(
            "core.installation_evidence_integrated_preview.verify_physical_inspection_candidate"
        ) as reviewer:
            projects.objects.select_related.return_value.filter.return_value.first.return_value = project
            inventory.return_value = [
                SimpleNamespace(unit_id=key) for key in units
            ]
            base.return_value = sentinel.existing_readiness
            reviewer.side_effect = lambda **args: SimpleNamespace(
                review_candidate_verified=args["unit_id"] in verified,
                blockers=() if args["unit_id"] in verified else ("No accepted review.",),
            )
            result = preview_installation_with_physical_reviews(
                project_id=self.project_id,
                installation_starts_at="2026-11-03T15:00:00+00:00",
            )
            return result, base, reviewer

    def test_every_reviewed_unit_still_cannot_authorize_start(self):
        result, base, reviewer = self.assess()
        self.assertEqual(result.total_units, 2)
        self.assertEqual(result.reviewed_candidate_units, 2)
        self.assertTrue(result.all_units_reviewed)
        self.assertIs(result.installation_assessment, sentinel.existing_readiness)
        self.assertFalse(result.trusted_installation_evidence)
        self.assertFalse(result.installation_authorized)
        self.assertEqual(reviewer.call_count, 2)
        base.assert_called_once()

    def test_missing_unit_review_is_reported(self):
        result, _, _ = self.assess(
            verified={"ROW-001-UNIT-001"}
        )
        self.assertEqual(result.reviewed_candidate_units, 1)
        self.assertFalse(result.all_units_reviewed)
        self.assertTrue(any(
            "ROW-002-UNIT-001" in item for item in result.blockers
        ))
        self.assertFalse(result.installation_authorized)

    def test_empty_unit_inventory_fails_closed(self):
        result, _, reviewer = self.assess(units=())
        self.assertEqual(result.total_units, 0)
        self.assertFalse(result.all_units_reviewed)
        self.assertFalse(result.installation_authorized)
        reviewer.assert_not_called()

    def test_cancelled_project_does_not_invoke_preview(self):
        cancelled = SimpleNamespace(
            state="CANCELLED",
            current_approved=self.project.current_approved,
        )
        result, base, reviewer = self.assess(project=cancelled)
        self.assertFalse(result.installation_authorized)
        self.assertTrue(result.blockers)
        base.assert_not_called()
        reviewer.assert_not_called()

    def test_wrong_msr_project_binding_fails_closed(self):
        wrong = SimpleNamespace(
            state="ACTIVE",
            current_approved=SimpleNamespace(
                pk=self.msr_id,
                project_id=str(uuid4()),
                status="APPROVED",
                snapshot={},
            ),
        )
        result, base, reviewer = self.assess(project=wrong)
        self.assertFalse(result.all_units_reviewed)
        self.assertFalse(result.installation_authorized)
        base.assert_not_called()
        reviewer.assert_not_called()