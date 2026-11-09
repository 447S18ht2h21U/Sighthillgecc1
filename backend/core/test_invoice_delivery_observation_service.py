"""Isolated synthetic Invoice observation database regression."""
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from . import tests as foundation
from .documents import generate
from .invoice_delivery_observation_service import (
    KIND, record_synthetic_invoice_observation,
)
from .models import AuditEvent, ProjectEvidence, Role, User


@override_settings(DEBUG=True, ENVIRONMENT='development')
class InvoiceObservationServiceTests(TestCase):
    setUp = foundation.FoundationTests.setUp
    edit_submit = foundation.FoundationTests.edit_submit
    approve = foundation.FoundationTests.approve

    def prepare(self):
        # Fictional recipient must be part of the approved MSR snapshot.
        self.snapshot["customer_email"] = "customer@example.invalid"
        approved = self.approve()
        self.project.refresh_from_db()
        document, _ = generate(self.manager, approved.pk, "INVOICE")
        now = timezone.now()
        preparer = self.manager
        candidate = {
            "msr_id": str(approved.pk),
            "document_id": str(document.pk),
            "invoice_sha256": document.pdf_sha256,
            "recipient_email": approved.snapshot["customer_email"],
            "channel": "PROVIDER_EMAIL",
            "provider_reference": "FICTIONAL-LOCAL-OBSERVATION",
            "delivered_at": now - timedelta(hours=2),
            "verified_by_id": str(self.comptroller.pk),
            "verified_at": now - timedelta(hours=1),
            "prepared_by_id": str(preparer.pk),
        }
        values = {
            "expected_account_id": str(uuid4()),
            "expected_envelope_id": str(uuid4()),
            "expected_provider_document_id": str(uuid4()),
            "expected_recipient_id": "1",
        }
        observation = {
            "account_id": values["expected_account_id"],
            "envelope_id": values["expected_envelope_id"],
            "document_id": values["expected_provider_document_id"],
            "recipient_id": "1",
            "recipient_email": approved.snapshot["customer_email"],
            "status": "delivered",
        }
        return document, candidate, values, observation

    def record(self, candidate, values, observation, actor=None):
        return record_synthetic_invoice_observation(
            actor or self.comptroller, self.project.pk,
            candidate["document_id"], candidate, observation, **values,
        )

    def test_observation_is_immutable_untrusted_and_audited(self):
        _, candidate, values, observation = self.prepare()
        evidence, created = self.record(candidate, values, observation)
        self.assertTrue(created)
        self.assertEqual(evidence.kind, KIND)
        self.assertFalse(evidence.data["verified"])
        self.assertFalse(evidence.data["trusted_delivery"])
        self.assertFalse(evidence.data["installation_evidence_accepted"])
        self.assertTrue(AuditEvent.objects.filter(
            action="invoice.delivery_observation_recorded"
        ).exists())

    def test_repeat_is_idempotent(self):
        _, candidate, values, observation = self.prepare()
        first, created = self.record(candidate, values, observation)
        self.assertTrue(created)
        second, created = self.record(candidate, values, observation)
        self.assertFalse(created)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(ProjectEvidence.objects.filter(kind=KIND).count(), 1)

    def test_mismatch_rejected(self):
        _, candidate, values, observation = self.prepare()
        candidate["invoice_sha256"] = "b" * 64
        with self.assertRaises(ValidationError):
            self.record(candidate, values, observation)
        self.assertFalse(ProjectEvidence.objects.filter(kind=KIND).exists())

    def test_wrong_recipient_rejected(self):
        _, candidate, values, observation = self.prepare()
        observation["recipient_email"] = "other@example.invalid"
        with self.assertRaises(ValidationError):
            self.record(candidate, values, observation)
        self.assertFalse(ProjectEvidence.objects.filter(kind=KIND).exists())

    def test_non_comptroller_rejected(self):
        _, candidate, values, observation = self.prepare()
        with self.assertRaises(PermissionDenied):
            self.record(candidate, values, observation, actor=self.manager)
        self.assertFalse(ProjectEvidence.objects.filter(kind=KIND).exists())

    def test_audit_failure_rolls_back_evidence(self):
        _, candidate, values, observation = self.prepare()
        with patch(
            "core.invoice_delivery_observation_service.audit",
            side_effect=RuntimeError("Synthetic audit failure"),
        ):
            with self.assertRaises(RuntimeError):
                self.record(candidate, values, observation)
        self.assertFalse(ProjectEvidence.objects.filter(kind=KIND).exists())

    def test_observation_does_not_change_installation_readiness(self):
        _, candidate, values, observation = self.prepare()
        from .installation_readiness import installation_readiness
        before = installation_readiness(self.project)
        self.record(candidate, values, observation)
        after = installation_readiness(self.project)
        self.assertEqual(before, after)
        self.assertFalse(after["eligible"])

    def test_production_environment_is_denied(self):
        _, candidate, values, observation = self.prepare()
        with override_settings(ENVIRONMENT="production", DEBUG=False):
            with self.assertRaises(ValidationError):
                self.record(candidate, values, observation)
        self.assertFalse(ProjectEvidence.objects.filter(kind=KIND).exists())

    def test_inactive_comptroller_is_denied(self):
        _, candidate, values, observation = self.prepare()
        User.objects.filter(pk=self.comptroller.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.record(candidate, values, observation)
        self.assertFalse(ProjectEvidence.objects.filter(kind=KIND).exists())

    def test_wrong_msr_reference_is_denied(self):
        _, candidate, values, observation = self.prepare()
        candidate["msr_id"] = str(uuid4())
        with self.assertRaises(ValidationError):
            self.record(candidate, values, observation)
        self.assertFalse(ProjectEvidence.objects.filter(kind=KIND).exists())

    def test_sent_without_delivery_is_denied(self):
        _, candidate, values, observation = self.prepare()
        observation["status"] = "sent"
        with self.assertRaises(ValidationError):
            self.record(candidate, values, observation)
        self.assertFalse(ProjectEvidence.objects.filter(kind=KIND).exists())