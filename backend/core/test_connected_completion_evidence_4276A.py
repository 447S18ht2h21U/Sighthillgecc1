"""Integrated fictional project completion-evidence acceptance.

No provider authentication, email sending, signature release, or completion.
"""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from .approved_project_workflow_checklist_4251 import (
    inspect_project_workflow_checklist,
)
from .completion_evidence_database_preview import (
    inspect_completion_database_evidence,
)
from .completion_evidence_policy_preview import (
    preview_project_completion_evidence,
)
from .completion_evidence_provenance_report import (
    inspect_completion_provenance,
)
from .models import Document
from .project_completion_authorization_guard import (
    require_verified_project_completion,
)
from .test_approved_document_lifecycle_integration_4249 import (
    RealLifecycleIntegration4249Tests,
)


class ConnectedCompletionEvidence4276ATests(TestCase):
    def setUp(self):
        RealLifecycleIntegration4249Tests.setUp(self)
        RealLifecycleIntegration4249Tests.prepare_no_promotion(self)
        self.snapshot_before = deepcopy(self.full_msr.snapshot)
        self.batch = RealLifecycleIntegration4249Tests.render(self)

    def verify_unchanged(self):
        self.full_msr.refresh_from_db()
        self.assertEqual(self.full_msr.snapshot, self.snapshot_before)
        self.assertEqual(Document.objects.count(), 0)

    def test_01_six_previews_cannot_satisfy_completion_evidence(self):
        checklist = inspect_project_workflow_checklist(
            project=self.project,
            msr=self.full_msr,
            batch=self.batch,
        )
        evidence = inspect_completion_database_evidence(
            project_id=str(self.project.pk),
        )
        provenance = inspect_completion_provenance(
            project_id=str(self.project.pk),
        )

        self.assertEqual(checklist.document_count, 6)
        self.assertFalse(checklist.project_completion_authorized)
        self.assertEqual(evidence.receipt_document_candidates, 0)
        self.assertEqual(evidence.certificate_document_candidates, 0)
        self.assertFalse(evidence.receipt_retention_verified)
        self.assertFalse(evidence.receipt_email_verified)
        self.assertFalse(evidence.completed_docusign_received_verified)
        self.assertFalse(evidence.completed_docusign_retained_verified)
        self.assertFalse(evidence.project_completion_authorized)
        self.assertFalse(evidence.project_completed)
        self.assertFalse(evidence.survey_required)

        self.assertEqual(provenance.approved_msr_id, str(self.full_msr.pk))
        self.assertEqual(provenance.receipt_pdf_candidates, 0)
        self.assertEqual(provenance.envelope_bound_certificate_candidates, 0)
        self.assertFalse(provenance.trusted_receipt_email)
        self.assertFalse(provenance.trusted_completed_docusign)
        self.assertFalse(provenance.completion_authorized)
        self.assertFalse(provenance.survey_required)

        self.verify_unchanged()
        print("PASS: Six real previews never become trusted completion evidence.")

    def test_02_each_mandatory_completion_condition_is_independent(self):
        required = {
            "physical_work_verified": True,
            "required_inspections_verified": True,
            "receipt_pdf_retained": True,
            "receipt_email_delivery_verified": True,
            "completed_docusign_certificate_received": True,
            "completed_docusign_certificate_retained": True,
        }

        complete_candidate = preview_project_completion_evidence(
            **required,
            customer_satisfaction_survey_received=False,
        )
        self.assertTrue(
            complete_candidate.candidate_requirements_satisfied
        )
        self.assertFalse(complete_candidate.evidence_trusted)
        self.assertFalse(
            complete_candidate.project_completion_authorized
        )
        self.assertFalse(complete_candidate.project_completed)
        self.assertTrue(complete_candidate.blockers)

        for field in required:
            flags = {**required, field: False}
            with self.subTest(missing=field):
                assessment = preview_project_completion_evidence(
                    **flags,
                    customer_satisfaction_survey_received=True,
                )
                self.assertFalse(
                    assessment.candidate_requirements_satisfied
                )
                self.assertGreater(
                    len(assessment.blockers),
                    len(complete_candidate.blockers),
                )
                self.assertFalse(assessment.evidence_trusted)
                self.assertFalse(
                    assessment.project_completion_authorized
                )

        self.verify_unchanged()
        print("PASS: Each of six mandatory completion conditions tested.")

    def test_03_optional_survey_never_changes_completion_eligibility(self):
        flags = {
            "physical_work_verified": True,
            "required_inspections_verified": True,
            "receipt_pdf_retained": True,
            "receipt_email_delivery_verified": True,
            "completed_docusign_certificate_received": True,
            "completed_docusign_certificate_retained": True,
        }

        without = preview_project_completion_evidence(
            **flags, customer_satisfaction_survey_received=False
        )
        with_survey = preview_project_completion_evidence(
            **flags, customer_satisfaction_survey_received=True
        )

        self.assertFalse(without.survey_received)
        self.assertTrue(with_survey.survey_received)
        self.assertEqual(
            without.candidate_requirements_satisfied,
            with_survey.candidate_requirements_satisfied,
        )
        self.assertEqual(without.blockers, with_survey.blockers)
        self.assertFalse(without.project_completion_authorized)
        self.assertFalse(with_survey.project_completion_authorized)

        self.verify_unchanged()
        print("PASS: Survey optional and never a completion blocker.")

    def test_04_forged_completion_claim_cannot_pass_guard(self):
        forged = SimpleNamespace(
            completion_authorized=True,
            project_completed=True,
            receipt_email_authenticated=True,
            docusign_completion_authenticated=True,
        )

        with patch(
            "core.project_completion_authorization_guard."
            "assess_project_completion_preflight",
            return_value=forged,
        ):
            with self.assertRaisesRegex(
            ValidationError,
            "Untrusted completion evidence cannot authorize a project",
        ):
                require_verified_project_completion(
                    actor=self.comptroller,
                    project_id=str(self.project.pk),
                )

        self.verify_unchanged()
        print("PASS: Forged completion authority rejected.")