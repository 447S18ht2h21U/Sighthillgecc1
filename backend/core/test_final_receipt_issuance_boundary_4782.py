"""Isolated database acceptance of Final Receipt issuance boundary.

Real Project, MSR, immutable Document, and outbox queries.
Only the upstream candidate-evidence assessment and internal
Receipt rendering inputs are controlled fixtures.
No external provider calls or customer issuance.
"""

from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from .final_receipt_issuance_boundary_4781 import (
    assess_final_receipt_issuance_boundary,
)
from .models import Document, ReceiptDispatchOutbox
from .test_final_receipt_retention_4773 import (
    InternalReceiptDatabaseAcceptance4773 as ReceiptFixture,
)


BOUNDARY = "core.final_receipt_issuance_boundary_4781"


@override_settings(DEBUG=True, ENVIRONMENT="development")
class FinalReceiptIssuanceDatabaseAcceptance4782(TestCase):
    setUp = ReceiptFixture.setUp
    patched_service = ReceiptFixture.patched_service
    create_internal = ReceiptFixture.create_internal

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        database = settings.DATABASES["default"]
        if (
            database["ENGINE"] != "django.db.backends.sqlite3"
            or not str(database["NAME"]).startswith(
                ("file:memorydb_default", ":memory:")
            )
        ):
            raise RuntimeError(
                "SAFETY STOP: Disposable SQLite database required."
            )

    def evidence_gate(self, **changes):
        values = {
            "project_id": str(self.project.pk),
            "approved_msr_id": str(self.msr.pk),
            "candidate_evidence_complete": True,
            "trusted_equipment_evidence": False,
            "retention_authorized": False,
            "final_receipt_verified": False,
            "customer_delivery_verified": False,
            "completion_authorized": False,
            "blockers": (),
        }
        values.update(changes)
        return SimpleNamespace(**values)

    @contextmanager
    def boundary(self, **gate_changes):
        with patch(
            BOUNDARY + ".assess_final_receipt_evidence_gate",
            return_value=self.evidence_gate(**gate_changes),
        ):
            yield

    def assert_never_authorized(self, outcome):
        self.assertFalse(outcome.trusted_installation_evidence)
        self.assertFalse(outcome.customer_receipt_issuance_authorized)
        self.assertFalse(outcome.provider_email_authenticated)
        self.assertFalse(outcome.customer_delivery_verified)
        self.assertFalse(outcome.completion_authorized)

    def test_no_document_remains_blocked(self):
        with self.boundary():
            outcome = assess_final_receipt_issuance_boundary(
                self.project
            )

        self.assertIsNone(outcome.internal_document_id)
        self.assertFalse(outcome.internal_document_verified)
        self.assertTrue(
            any("No retained internal" in s for s in outcome.blockers)
        )
        self.assert_never_authorized(outcome)
        self.assertEqual(Document.objects.count(), 0)
        print("PASS: Missing document cannot authorize issuance.")

    def test_real_immutable_document_remains_internal_only(self):
        with self.patched_service()[0]:
            saved, created = self.create_internal()

        self.assertTrue(created)

        with self.boundary():
            outcome = assess_final_receipt_issuance_boundary(
                self.project
            )

        self.assertEqual(outcome.internal_document_id, str(saved.pk))
        self.assertTrue(outcome.internal_document_verified)
        self.assertTrue(outcome.reviewed_equipment_candidates_complete)
        self.assertEqual(outcome.existing_outbox_intents, 0)
        self.assertTrue(
            any("INTERNAL preparation" in s for s in outcome.blockers)
        )
        self.assert_never_authorized(outcome)

        retained = Document.objects.get(pk=saved.pk)
        self.assertEqual(retained.status, "PREPARATION")
        self.assertEqual(
            retained.values["purpose"], "INTERNAL_NOT_ISSUED"
        )
        self.assertEqual(ReceiptDispatchOutbox.objects.count(), 0)
        print(
            "PASS: Real immutable internal PDF verified but never issued."
        )

    def test_database_tamper_rejected_and_boundary_preserved(self):
        with self.patched_service()[0]:
            saved, _ = self.create_internal()

        original = bytes(
            Document.objects.get(pk=saved.pk).content
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Document.objects.filter(pk=saved.pk).update(
                    content=original + b"CORRUPTION"
                )

        self.assertEqual(
            bytes(Document.objects.get(pk=saved.pk).content),
            original,
        )

        with self.boundary():
            outcome = assess_final_receipt_issuance_boundary(
                self.project
            )

        self.assertTrue(outcome.internal_document_verified)
        self.assert_never_authorized(outcome)
        self.assertEqual(Document.objects.count(), 1)
        print(
            "PASS: Database rejects tamper and retains issuance block."
        )

    def test_false_trust_and_cross_msr_are_rejected(self):
        with self.boundary(trusted_equipment_evidence=True):
            with self.assertRaises(ValueError):
                assess_final_receipt_issuance_boundary(
                    self.project
                )

        with self.boundary(approved_msr_id="FOREIGN-MSR"):
            with self.assertRaises(ValueError):
                assess_final_receipt_issuance_boundary(
                    self.project
                )

        with self.boundary(
            customer_delivery_verified=True
        ):
            with self.assertRaises(ValueError):
                assess_final_receipt_issuance_boundary(
                    self.project
                )

        self.assertEqual(Document.objects.count(), 0)
        print(
            "PASS: False trust, cross-MSR, and delivery claims denied."
        )
