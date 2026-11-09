"""Real SQLite Receipt tests: customer email entered BEFORE MSR approval."""
import hashlib
from datetime import timedelta

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.mail import get_connection
from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from .models import Document, ReceiptSendingObservation, Role, User
from .receipt_secure_test_workflow import secure_test_receipt_dispatch
from . import test_installation_combined_real_evidence as foundation


class RealReceiptWorkflowTests(TestCase):
    def setUp(self):
        fixture = foundation.RealTwoStageDatabaseRegressionTests()
        fixture.setUp()

        # Set the email before approval. NEVER update an approved MSR.
        fixture.snapshot["customer_email"] = "customer@example.com"
        self.msr = fixture.prepare()
        self.actor = User.objects.get(pk=self.msr.created_by_id)
        self.actor.role = Role.COMPTROLLER
        self.actor.is_active = True
        self.actor.save(update_fields=["role", "is_active"])

        self.pdf = b"%PDF-1.4\nRetained test Receipt\n%%EOF"
        self.digest = hashlib.sha256(self.pdf).hexdigest()
        self.document = Document.objects.create(
            msr=self.msr,
            kind=Document.Kind.INVOICE,
            status="PREPARATION",
            created_by=self.actor,
            filename="historical-invoice-candidate.pdf",
            template_sha256="a" * 64,
            snapshot_sha256="b" * 64,
            pdf_sha256=self.digest,
            renderer_version="1",
            values={},
            content=self.pdf,
        )
        self.values = dict(
            actor=self.actor,
            project_id=self.msr.project_id,
            document_id=self.document.pk,
            recipient="customer@example.com",
            pdf_bytes=self.pdf,
            observed_sent_at=timezone.now() - timedelta(minutes=1),
            connection=get_connection(
                backend="django.core.mail.backends.locmem.EmailBackend"
            ),
            provider_reference="TEST-4141",
        )

    def run_workflow(self, **changes):
        values = dict(self.values)
        values.update(changes)
        return secure_test_receipt_dispatch(**values)

    def test_real_project_document_and_observation(self):
        record = self.run_workflow()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(ReceiptSendingObservation.objects.count(), 1)
        self.assertEqual(record.status, "UNVERIFIED")
        self.assertEqual(record.msr_id, self.msr.pk)
        self.assertEqual(record.document_id, self.document.pk)
        self.assertEqual(mail.outbox[0].attachments[0][1], self.pdf)
        self.assertEqual(record.pdf_sha256, self.digest)

    def test_wrong_customer_does_not_send(self):
        with self.assertRaises(ValidationError):
            self.run_workflow(recipient="other@example.com")
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(ReceiptSendingObservation.objects.exists())

    def test_changed_pdf_does_not_send(self):
        with self.assertRaises(ValidationError):
            self.run_workflow(pdf_bytes=b"%PDF-1.4\nModified\n%%EOF")
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(ReceiptSendingObservation.objects.exists())

    def test_inactive_comptroller_does_not_send(self):
        self.actor.is_active = False
        self.actor.save(update_fields=["is_active"])
        with self.assertRaises(PermissionDenied):
            self.run_workflow()
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(ReceiptSendingObservation.objects.exists())

    def test_other_role_does_not_send(self):
        self.actor.role = Role.SALES_ASSOCIATE
        self.actor.save(update_fields=["role"])
        with self.assertRaises(PermissionDenied):
            self.run_workflow()
        self.assertEqual(len(mail.outbox), 0)
        self.assertFalse(ReceiptSendingObservation.objects.exists())