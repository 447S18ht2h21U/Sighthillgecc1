"""Fail-closed completion provenance regression tests."""
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
from uuid import uuid4

from django.test import SimpleTestCase, TestCase

from .completion_evidence_provenance_report import (
    inspect_completion_provenance,
)
from . import test_installation_combined_real_evidence as fixtures


class CompletionProvenanceMockTests(SimpleTestCase):
    def setUp(self):
        self.project_id = str(uuid4())
        self.msr_id = uuid4()
        self.msr = SimpleNamespace(
            pk=self.msr_id,
            project_id=self.project_id,
            status="APPROVED",
        )
        self.project = SimpleNamespace(
            pk=self.project_id,
            state="APPROVED",
            current_approved=self.msr,
        )

    def assess(self, *, project=None, synthetic=0,
               verifications=(), documents=()):
        chosen = self.project if project is None else project

        with patch(
            "core.completion_evidence_provenance_report.Project"
        ) as projects, patch(
            "core.completion_evidence_provenance_report.Document"
        ) as stored, patch(
            "core.completion_evidence_provenance_report.ProjectEvidence"
        ) as evidence, patch(
            "core.completion_evidence_provenance_report.CompletionSignatureVerification"
        ) as signatures, patch(
            "core.completion_evidence_provenance_report.CompletionEnvelopeAttempt"
        ) as attempts:
            projects.objects.select_related.return_value.filter.return_value.first.return_value = chosen
            stored.objects.filter.return_value = list(documents)
            evidence.objects.filter.return_value.count.return_value = synthetic
            signatures.objects.filter.return_value.select_related.return_value = list(verifications)
            attempts.objects.filter.return_value.__getitem__.return_value = []
            return inspect_completion_provenance(
                project_id=self.project_id
            )

    def test_missing_approved_msr_is_denied(self):
        project = SimpleNamespace(
            pk=self.project_id,
            state="APPROVED",
            current_approved=None,
        )
        r = self.assess(project=project)
        self.assertIsNone(r.approved_msr_id)
        self.assertFalse(r.completion_authorized)

    def test_empty_records_are_denied(self):
        r = self.assess()
        self.assertEqual(r.receipt_pdf_candidates, 0)
        self.assertEqual(r.envelope_bound_certificate_candidates, 0)
        self.assertFalse(r.trusted_receipt_email)
        self.assertFalse(r.trusted_completed_docusign)

    def test_synthetic_email_observation_never_proves_delivery(self):
        r = self.assess(synthetic=5)
        self.assertEqual(r.synthetic_email_observations, 5)
        self.assertFalse(r.trusted_receipt_email)
        self.assertFalse(r.completion_authorized)

    def test_forged_completed_provider_metadata_is_not_trusted(self):
        verification = SimpleNamespace(
            release_package=SimpleNamespace(
                plan=SimpleNamespace(group="COMPLETION_FINANCED")
            ),
            provider_account_id=str(uuid4()),
            provider_envelope_id=str(uuid4()),
            evidence={"status": "completed", "verified": True},
        )
        r = self.assess(verifications=[verification])
        self.assertFalse(r.trusted_completed_docusign)
        self.assertFalse(r.completion_authorized)

    def test_cancelled_project_is_denied(self):
        self.project.state = "CANCELLED"
        r = self.assess()
        self.assertTrue(any("Cancelled" in x for x in r.blockers))
        self.assertFalse(r.completion_authorized)

    def test_invalid_project_id_is_rejected(self):
        with self.assertRaises(ValueError):
            inspect_completion_provenance(project_id="not-a-uuid")

    def test_survey_is_never_required(self):
        r = self.assess()
        self.assertFalse(r.survey_required)
        self.assertFalse(r.completion_authorized)


class CompletionProvenanceDatabaseTests(TestCase):
    def test_actual_database_project_without_proof_is_denied(self):
        fixture = fixtures.RealTwoStageDatabaseRegressionTests()
        fixture.setUp()
        msr = fixture.prepare()

        report = inspect_completion_provenance(
            project_id=str(fixture.project.pk)
        )

        self.assertEqual(report.approved_msr_id, str(msr.pk))
        self.assertEqual(report.receipt_pdf_candidates, 0)
        self.assertEqual(report.synthetic_email_observations, 0)
        self.assertEqual(
            report.envelope_bound_certificate_candidates, 0
        )
        self.assertFalse(report.trusted_receipt_email)
        self.assertFalse(report.trusted_completed_docusign)
        self.assertFalse(report.survey_required)
        self.assertFalse(report.completion_authorized)