"""Fail-closed evidence projection security regressions."""
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from .dashboard_workflow_evidence_4257 import (
    describe_workflow_evidence,
)


class DashboardWorkflowEvidence4257Tests(SimpleTestCase):
    def setUp(self):
        self.msr = SimpleNamespace(
            status="APPROVED",
            project_id="project-1",
        )
        self.project = SimpleNamespace(
            pk="project-1",
            state="APPROVED",
            current_approved=self.msr,
        )

    def test_verified_prerequisite_checks_are_not_approval(self):
        result = {
            "eligible": True,
            "requirements": {
                "approved_msr": True,
                "contract_signed": True,
                "cancellation_complete": True,
                "waiting_period_complete": True,
                "deposit_verified": True,
            },
            "blocking_reasons": [],
        }
        with patch(
            "core.dashboard_workflow_evidence_4257.installation_readiness",
            return_value=result,
        ):
            summary = describe_workflow_evidence(self.project)

        self.assertEqual(
            summary["statuses"]["contract_signature"],
            "CHECK_PASSED",
        )
        self.assertEqual(
            summary["statuses"]["payment_readiness"],
            "CHECK_PASSED",
        )
        self.assertFalse(summary["installation_authorized"])
        self.assertFalse(summary["project_completion_authorized"])
        self.assertEqual(
            summary["statuses"]["project_completion"], "BLOCKED"
        )

    def test_failed_prerequisites_stay_blocked(self):
        result = {
            "eligible": False,
            "requirements": {
                "contract_signed": False,
                "cancellation_complete": False,
                "waiting_period_complete": False,
                "deposit_verified": False,
            },
            "blocking_reasons": ["Missing verified evidence."],
        }
        with patch(
            "core.dashboard_workflow_evidence_4257.installation_readiness",
            return_value=result,
        ):
            summary = describe_workflow_evidence(self.project)

        for key in (
            "contract_signature",
            "cancellation_deadline",
            "waiting_period",
            "payment_readiness",
        ):
            self.assertEqual(summary["statuses"][key], "BLOCKED")

    def test_no_approved_msr_does_not_run_readiness(self):
        self.project.current_approved = None
        with patch(
            "core.dashboard_workflow_evidence_4257.installation_readiness"
        ) as readiness:
            summary = describe_workflow_evidence(self.project)

        readiness.assert_not_called()
        self.assertEqual(
            summary["statuses"]["approved_msr"], "BLOCKED"
        )

    def test_cancelled_project_does_not_run_readiness(self):
        self.project.state = "CANCELLED"
        with patch(
            "core.dashboard_workflow_evidence_4257.installation_readiness"
        ) as readiness:
            summary = describe_workflow_evidence(self.project)

        readiness.assert_not_called()
        self.assertEqual(
            summary["statuses"]["project_completion"], "BLOCKED"
        )

    def test_mismatched_msr_binding_is_rejected(self):
        self.msr.project_id = "another-project"
        with patch(
            "core.dashboard_workflow_evidence_4257.installation_readiness"
        ) as readiness:
            summary = describe_workflow_evidence(self.project)

        readiness.assert_not_called()
        self.assertEqual(
            summary["statuses"]["approved_msr"], "BLOCKED"
        )

    def test_service_failure_does_not_create_approval(self):
        with patch(
            "core.dashboard_workflow_evidence_4257.installation_readiness",
            side_effect=RuntimeError("Service unavailable"),
        ):
            summary = describe_workflow_evidence(self.project)

        self.assertEqual(
            summary["statuses"]["payment_readiness"],
            "NOT_EVALUATED",
        )
        self.assertFalse(summary["installation_authorized"])
        self.assertFalse(summary["project_completion_authorized"])

    def test_missing_scope_record_is_rejected(self):
        with self.assertRaises(ValueError):
            describe_workflow_evidence(None)

    def test_receipt_and_docusign_never_inferred(self):
        summary = describe_workflow_evidence(
            SimpleNamespace(
                pk="project-1",
                state="DRAFT",
                current_approved=None,
            )
        )
        self.assertEqual(
            summary["statuses"]["receipt_delivery"],
            "NOT_EVALUATED",
        )
        self.assertEqual(
            summary["statuses"]["completed_docusign"],
            "NOT_EVALUATED",
        )