"""Focused fail-closed completion evidence checks."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, TestCase

from .completion_evidence_database_preview import (
    inspect_completion_database_evidence,
)
from . import test_installation_combined_real_evidence as fixture_module


class CompletionEvidenceServiceTests(SimpleTestCase):
    def setUp(self):
        self.key = str(uuid4())
        self.msr_key = uuid4()
        self.msr = SimpleNamespace(
            pk=self.msr_key,
            status="APPROVED",
            project_id=self.key,
            snapshot={"financing_type": "FINANCED"},
        )
        self.project = SimpleNamespace(
            pk=self.key,
            state="ACTIVE",
            current_approved=self.msr,
        )

    def run_preview(self, project):
        with patch(
            "core.completion_evidence_database_preview.Project"
        ) as projects, patch(
            "core.completion_evidence_database_preview.Document"
        ) as documents, patch(
            "core.completion_evidence_database_preview.CompletionSignatureVerification"
        ) as verifications:
            projects.objects.select_related.return_value.filter.return_value.first.return_value = project
            documents.objects.filter.return_value = []
            verifications.objects.filter.return_value = []
            report = inspect_completion_database_evidence(
                project_id=self.key
            )
            return report

    def test_missing_project_fails_closed(self):
        report = self.run_preview(None)
        self.assertIsNone(report.msr_id)
        self.assertFalse(report.project_completion_authorized)

    def test_missing_approved_msr_fails_closed(self):
        self.project.current_approved = None
        report = self.run_preview(self.project)
        self.assertTrue(any("approved MSR" in b for b in report.blockers))
        self.assertFalse(report.project_completed)

    def test_no_receipt_or_certificate_fails_closed(self):
        report = self.run_preview(self.project)
        self.assertEqual(report.receipt_document_candidates, 0)
        self.assertEqual(report.certificate_document_candidates, 0)
        self.assertFalse(report.receipt_email_verified)
        self.assertFalse(report.completed_docusign_received_verified)

    def test_cancelled_project_fails_closed(self):
        self.project.state = "CANCELLED"
        report = self.run_preview(self.project)
        self.assertTrue(any("Cancelled" in b for b in report.blockers))
        self.assertFalse(report.project_completion_authorized)

    def test_invalid_financing_cannot_verify_certificate(self):
        self.msr.snapshot = {"financing_type": "UNKNOWN"}
        report = self.run_preview(self.project)
        self.assertTrue(any("financing" in b for b in report.blockers))
        self.assertFalse(report.completed_docusign_retained_verified)


class CompletionEvidenceRealDatabaseTests(TestCase):
    def test_real_project_without_receipt_delivery_or_certificate_denied(self):
        fixture = fixture_module.RealTwoStageDatabaseRegressionTests()
        fixture.setUp()
        msr = fixture.prepare()
        project = fixture.project

        report = inspect_completion_database_evidence(
            project_id=str(project.pk)
        )

        self.assertEqual(report.project_id, str(project.pk))
        self.assertEqual(report.msr_id, str(msr.pk))
        self.assertFalse(report.receipt_retention_verified)
        self.assertFalse(report.receipt_email_verified)
        self.assertFalse(report.completed_docusign_received_verified)
        self.assertFalse(report.completed_docusign_retained_verified)
        self.assertFalse(report.survey_required)
        self.assertFalse(report.project_completion_authorized)
        self.assertFalse(report.project_completed)
        self.assertTrue(report.blockers)