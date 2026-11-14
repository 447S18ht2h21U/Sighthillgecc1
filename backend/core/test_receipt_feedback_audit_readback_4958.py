"""Real database acceptance of persisted feedback audit readback."""

from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied

from .models import User, Role, ProjectEvidence
from .test_receipt_feedback_db_4956 import (
    ReceiptFeedbackDatabaseAcceptance4956 as Fixture4956,
)
from .receipt_feedback_audit_readback_4958 import (
    read_project_receipt_audit,
)


@override_settings(DEBUG=True, ENVIRONMENT="development")
class PersistedReceiptAuditAcceptance4958(TestCase):
    def setUp(self):
        # Reuse the previously accepted, actual ORM fixture,
        # without inheriting and rerunning its unrelated test methods.
        Fixture4956.setUp(self)

        with patch(
            "core.receipt_feedback_record_4954.audit"
        ):
            self.evidence, created = Fixture4956.retain(self)

        self.assertTrue(created)
        self.evidence.refresh_from_db()

        self.findings = {
            f"inspection_{index}": "YES"
            for index in range(1, 6)
        }
        self.arguments = dict(
            actor=self.actor,
            project_id=self.project.pk,
            feedback_evidence_id=self.evidence.pk,
            inspection_source_evidence_id="SYNTHETIC-INSPECTION-4958",
            manager_findings=self.findings,
        )

    def test_persisted_evidence_produces_read_only_audit(self):
        result = read_project_receipt_audit(**self.arguments)

        self.assertEqual(
            result.feedback_evidence_id, str(self.evidence.pk)
        )
        self.assertEqual(
            result.project_id, str(self.project.pk)
        )
        self.assertEqual(
            result.packet.audit.direct_discrepancy_ids,
            ("survey_1",),
        )
        self.assertEqual(
            result.packet.audit.review_candidate_ids,
            ("inspection_4",),
        )
        self.assertFalse(result.customer_provenance_authenticated)
        self.assertFalse(result.receipt_pdf_independently_verified)
        self.assertFalse(result.inspection_signature_verified)
        self.assertFalse(result.work_orders_created)
        self.assertFalse(result.project_completion_authorized)

    def test_wrong_evidence_identity_rejected(self):
        values = {
            **self.arguments,
            "feedback_evidence_id": "00000000-0000-0000-0000-000000000000",
        }
        with self.assertRaises(ValidationError):
            read_project_receipt_audit(**values)

    def test_wrong_project_rejected(self):
        values = {
            **self.arguments,
            "project_id": "00000000-0000-0000-0000-000000000000",
        }
        with self.assertRaises(ValidationError):
            read_project_receipt_audit(**values)

    def test_technician_cannot_read_project_feedback(self):
        technician = User.objects.create_user(
            username="receipt-feedback-reader-4958",
            password=None,
            role=Role.TECHNICIAN,
            initials="RA",
        )
        with self.assertRaises(PermissionDenied):
            read_project_receipt_audit(
                **{**self.arguments, "actor": technician}
            )

    def test_tampered_evidence_fingerprint_rejected(self):
        # No mutation of the persisted immutable evidence.
        # Test integrity using a simulated corrupted readback.
        damaged = ProjectEvidence.objects.get(
            pk=self.evidence.pk
        )
        damaged.digest = "0" * 64

        with patch(
            "core.receipt_feedback_audit_readback_4958.ProjectEvidence.objects.filter"
        ) as filtered:
            filtered.return_value.first.return_value = damaged
            with self.assertRaises(ValidationError):
                read_project_receipt_audit(**self.arguments)
