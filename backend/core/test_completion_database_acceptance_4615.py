"""Disposable SQLite acceptance of completion evidence relationships."""
import hashlib
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from . import test_installation_combined_real_evidence as fixtures
from .models import (
    CompletionSignatureVerification,
    Document,
    ReceiptDispatchOutbox,
    ReceiptSendingObservation,
)
from .receipt_evidence_chain_4613 import inspect_receipt_chain
from .completion_retention_4612 import retain_authenticated_completion


class CompletionDatabaseAcceptanceTests(TestCase):
    def setUp(self):
        fixture = fixtures.RealTwoStageDatabaseRegressionTests()
        fixture.setUp()
        # Set the synthetic customer email before the normal MSR
        # approval process. Never modify an approved MSR.
        fixture.snapshot["customer_email"] = (
            "synthetic.receipt@example.test"
        )
        fixture.prepare()

        self.project = fixture.project
        self.comptroller = fixture.comptroller
        self.project.refresh_from_db()
        self.msr = self.project.current_approved

        self.email = self.msr.snapshot.get("customer_email")
        self.assertIsInstance(self.email, str)
        self.assertTrue(self.email.strip())

        self.pdf = b"%PDF-1.4\\nsynthetic acceptance receipt"
        self.digest = hashlib.sha256(self.pdf).hexdigest()

        self.document = Document.objects.create(
            msr=self.msr,
            kind=Document.Kind.INVOICE,
            created_by=self.comptroller,
            status="PREPARATION",
            filename="synthetic-receipt-candidate.pdf",
            template_sha256="a" * 64,
            snapshot_sha256="b" * 64,
            pdf_sha256=self.digest,
            renderer_version="test-4615",
            values={},
            content=self.pdf,
        )

    def record_candidates(self):
        ReceiptDispatchOutbox.objects.create(
            project=self.project,
            msr=self.msr,
            document=self.document,
            requested_by=self.comptroller,
            idempotency_key="acceptance4615",
            recipient_email=self.email,
            pdf_sha256=self.digest,
            status="PENDING",
        )
        ReceiptSendingObservation.objects.create(
            msr=self.msr,
            document=self.document,
            recorded_by=self.comptroller,
            recipient_email=self.email,
            provider_reference="SYNTHETIC-NOT-A-PROVIDER-ID",
            sent_at=timezone.now() - timedelta(minutes=1),
            pdf_sha256=self.digest,
            observation_source="MANUAL_OBSERVATION",
            status="UNVERIFIED",
        )

    def test_real_database_candidates_remain_untrusted(self):
        self.record_candidates()

        before = self.project.state
        result = inspect_receipt_chain(self.project)

        self.assertEqual(result["valid_pdf_candidates"], 1)
        self.assertEqual(result["matching_outbox_intents"], 1)
        self.assertEqual(result["matching_local_observations"], 1)
        self.assertFalse(result["final_receipt_verified"])
        self.assertFalse(result["provider_email_authenticated"])
        self.assertFalse(result["completion_authorized"])

        self.project.refresh_from_db()
        self.assertEqual(self.project.state, before)

    def test_database_fingerprint_tampering_blocks_matches(self):
        self.record_candidates()

        # The SQLite database trigger must reject even a direct
        # QuerySet.update() attempt. Never disable the trigger.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Document.objects.filter(pk=self.document.pk).update(
                    content=self.pdf + b"tampered"
                )

        self.document.refresh_from_db()
        self.assertEqual(bytes(self.document.content), self.pdf)

        result = inspect_receipt_chain(self.project)
        self.assertEqual(result["valid_pdf_candidates"], 1)
        self.assertEqual(result["matching_outbox_intents"], 1)
        self.assertEqual(result["matching_local_observations"], 1)
        self.assertFalse(result["provider_email_authenticated"])
        self.assertFalse(result["completion_authorized"])

    def test_database_outbox_recipient_mismatch_fails_closed(self):
        self.record_candidates()

        # An immutable outbox cannot have its recipient replaced,
        # even via a direct database UPDATE.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ReceiptDispatchOutbox.objects.filter(
                    project=self.project
                ).update(recipient_email="wrong@example.test")

        entry = ReceiptDispatchOutbox.objects.get(
            project=self.project
        )
        self.assertEqual(
            entry.recipient_email.casefold(),
            self.email.casefold(),
        )

        result = inspect_receipt_chain(self.project)
        self.assertEqual(result["valid_pdf_candidates"], 1)
        self.assertEqual(result["matching_outbox_intents"], 1)
        self.assertFalse(result["provider_email_authenticated"])
        self.assertFalse(result["completion_authorized"])

    @override_settings(ENVIRONMENT="development", DEBUG=True)
    def test_retention_activation_disabled_before_database_write(self):
        initial = CompletionSignatureVerification.objects.count()

        with patch.dict(
            "os.environ",
            {"GECC_SANDBOX_COMPLETION_RETENTION_ENABLED": "0"},
        ):
            with self.assertRaises(ValidationError):
                retain_authenticated_completion(
                    actor=self.comptroller,
                    attempt_id=str(self.project.pk),
                    challenge=None,
                    evidence={},
                )

        self.assertEqual(
            CompletionSignatureVerification.objects.count(),
            initial,
        )
