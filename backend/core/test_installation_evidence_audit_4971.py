"""Real disposable-database readback of inspection + optional Receipt."""
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.exceptions import PermissionDenied

from .models import Role, User
from .test_installation_evidence_retention_4969 import (
    InspectionEvidenceDatabaseAcceptance4969 as Fixture,
)
from .test_receipt_feedback_db_4956 import (
    ReceiptFeedbackDatabaseAcceptance4956 as ReceiptFixture,
)
from .installation_evidence_retention_4969 import (
    retain_unverified_inspection_evidence,
)
from .installation_evidence_audit_4971 import (
    read_retained_inspection_project_audit,
)

WRITER = "core.installation_evidence_retention_4969"
RECEIPT_WRITER = "core.receipt_feedback_record_4954"


@override_settings(DEBUG=True, ENVIRONMENT="development")
class RetainedInspectionAuditDatabase4971(TestCase):
    def setUp(self):
        Fixture.setUp(self)
        with patch(WRITER + ".audit"):
            self.record, created = retain_unverified_inspection_evidence(
                actor=self.actor,
                project_id=self.project.pk,
                bundle=self.bundle,
            )
        self.assertTrue(created)

    def read(self, **changes):
        arguments = dict(
            actor=self.actor,
            project_id=self.project.pk,
            inspection_evidence_id=self.record.pk,
        )
        arguments.update(changes)
        return read_retained_inspection_project_audit(**arguments)

    def test_actual_immutable_record_readback(self):
        result = self.read()
        self.assertEqual(result.inspection_evidence_id, str(self.record.pk))
        self.assertEqual(result.project_id, str(self.project.pk))
        self.assertEqual(result.approved_msr_id, str(self.msr.pk))
        self.assertEqual(len(result.inspection_findings), 5)
        self.assertTrue(result.retained_bytes_integrity_verified)
        self.assertIsNone(result.receipt_comparison)
        self.assertFalse(result.provider_origin_authenticated)
        self.assertFalse(result.manager_signature_verified)
        self.assertFalse(result.project_completion_authorized)

    def test_existing_receipt_feedback_connected_to_audit(self):
        with patch(RECEIPT_WRITER + ".audit"):
            feedback, created = ReceiptFixture.retain(self)
        self.assertTrue(created)

        result = self.read(receipt_feedback_evidence_id=feedback.pk)
        self.assertEqual(
            result.receipt_feedback_evidence_id, str(feedback.pk)
        )
        self.assertIsNotNone(result.receipt_comparison)
        self.assertFalse(result.customer_feedback_authenticated)
        self.assertFalse(result.corrective_actions_created)
        self.assertFalse(result.project_completion_authorized)

    def test_wrong_inspection_evidence_rejected(self):
        with self.assertRaises(ValidationError):
            self.read(
                inspection_evidence_id=
                "00000000-0000-0000-0000-000000000000"
            )

    def test_missing_receipt_evidence_rejected(self):
        with self.assertRaises(ValidationError):
            self.read(
                receipt_feedback_evidence_id=
                "00000000-0000-0000-0000-000000000000"
            )

    def test_technician_cannot_read_inspection_evidence(self):
        technician = User.objects.create_user(
            username="inspection-readback-tech-4971",
            password=None,
            role=Role.TECHNICIAN,
            initials="IT",
        )
        with self.assertRaises(PermissionDenied):
            self.read(actor=technician)
