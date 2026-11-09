"""Real isolated-DB safeguards for untrusted Receipt-sending records."""
import hashlib
from datetime import timedelta
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from .models import Document, ReceiptSendingObservation
from . import test_installation_combined_real_evidence as fixtures


class ReceiptSendingObservationTests(TestCase):
    def setUp(self):
        fixture = fixtures.RealTwoStageDatabaseRegressionTests()
        fixture.setUp()
        self.msr = fixture.prepare()
        self.actor = self.msr.created_by
        self.pdf = b"%PDF-1.4\nSample retained Receipt\n%%EOF"
        self.sha = hashlib.sha256(self.pdf).hexdigest()
        self.document = Document.objects.create(
            msr=self.msr,
            kind="INVOICE",
            status="PREPARATION",
            created_by=self.actor,
            filename="historical-invoice-candidate.pdf",
            template_sha256="a" * 64,
            snapshot_sha256="b" * 64,
            pdf_sha256=self.sha,
            renderer_version="1",
            values={},
            content=self.pdf,
        )

    def candidate(self, **changes):
        values = dict(
            msr=self.msr,
            document=self.document,
            recorded_by=self.actor,
            recipient_email="customer@example.com",
            provider_reference="candidate-123",
            sent_at=timezone.now() - timedelta(minutes=1),
            pdf_sha256=self.sha,
            observation_source="MANUAL_OBSERVATION",
            status="UNVERIFIED",
        )
        values.update(changes)
        return ReceiptSendingObservation(**values)

    def test_record_remains_unverified(self):
        obj = self.candidate()
        obj.save()
        loaded = ReceiptSendingObservation.objects.get(pk=obj.pk)
        self.assertEqual(loaded.status, "UNVERIFIED")
        self.assertEqual(loaded.document_id, self.document.pk)
        self.assertEqual(loaded.msr_id, self.msr.pk)

    def test_cannot_claim_trusted_sending(self):
        with self.assertRaises(ValidationError):
            self.candidate(status="VERIFIED").save()

    def test_wrong_pdf_fingerprint_rejected(self):
        with self.assertRaises(ValidationError):
            self.candidate(pdf_sha256="0" * 64).save()

    def test_mismatched_document_msr_rejected(self):
        other = self.candidate()
        other.msr_id = uuid4()
        with self.assertRaises(ValidationError):
            other.save()

    def test_saved_record_cannot_be_changed_or_deleted(self):
        record = self.candidate()
        record.save()
        record.provider_reference = "changed"
        with self.assertRaises(ValidationError):
            record.save()
        with self.assertRaises(ValidationError):
            record.delete()
        self.assertEqual(
            ReceiptSendingObservation.objects.get(pk=record.pk).provider_reference,
            "candidate-123",
        )

    def test_future_and_naive_times_rejected(self):
        for time_value in (
            timezone.now() + timedelta(days=1),
            timezone.now().replace(tzinfo=None),
        ):
            with self.subTest(time_value=time_value):
                with self.assertRaises(ValidationError):
                    self.candidate(sent_at=time_value).save()
