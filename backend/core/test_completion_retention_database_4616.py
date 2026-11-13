"""Synthetic database acceptance for immutable completion retention.

No network requests, provider authentication, operational database,
or production send authorization. Release approval is explicitly mocked.
"""
import hashlib
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase, override_settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from . import test_installation_combined_real_evidence as fixtures
from .completion_retention_4612 import retain_authenticated_completion
from .models import (
    CompletionEnvelopeAttempt,
    CompletionSignatureVerification,
    CompletionSignatureDocument,
    DocusignChallenge,
    ReleasePackage,
    SigningPlan,
)


@override_settings(ENVIRONMENT="development", DEBUG=True)
class CompletionRetentionDatabaseTests(TestCase):
    def setUp(self):
        fixture = fixtures.RealTwoStageDatabaseRegressionTests()
        fixture.setUp()
        fixture.prepare()

        self.project = fixture.project
        self.comptroller = fixture.comptroller
        self.project.refresh_from_db()
        self.msr = self.project.current_approved

        group = "COMPLETION_" + self.msr.snapshot["financing_type"]

        self.plan = SigningPlan.objects.create(
            msr=self.msr,
            group=group,
            created_by=self.comptroller,
            review={
                "envelope_preview": {
                    "documents": [
                        {"documentId": "1", "name": "Completion.pdf"}
                    ],
                    "recipients": {"signers": []},
                }
            },
            digest="a" * 64,
        )

        self.package = ReleasePackage.objects.create(
            plan=self.plan,
            created_by=self.comptroller,
            payload={"synthetic_test_only": True},
            digest="b" * 64,
        )

        self.account = str(uuid4())
        self.envelope = str(uuid4())

        self.attempt = CompletionEnvelopeAttempt.objects.create(
            release_package=self.package,
            initiated_by=self.comptroller,
            provider_account_id=self.account,
            provider_envelope_id="",
            state="AUTH_PENDING",
            first_send_started_at=None,
        )

        self.context = {
            "operation": "SANDBOX_COMPLETION_READ",
            "completion_attempt_id": str(self.attempt.pk),
            "release_package_id": str(self.package.pk),
            "release_package_digest": self.package.digest,
            "project_id": str(self.project.pk),
            "msr_id": str(self.msr.pk),
            "account_id": self.account,
            "envelope_id": self.envelope,
        }

        self.challenge = DocusignChallenge.objects.create(
            actor=self.comptroller,
            state_digest=uuid4().hex,
            session_digest=uuid4().hex,
            configuration_digest=uuid4().hex,
            expires_at=timezone.now() + timedelta(minutes=5),
            consumed_at=timezone.now(),
            context=self.context,
        )

        self.pdf = b"%PDF-1.4\\nsynthetic signed document"
        self.certificate = b"%PDF-1.4\\nsynthetic audit certificate"

        self.evidence = {
            "provider": "DOCUSIGN_SANDBOX",
            "provider_response_validated": True,
            "completion_authorized": False,
            "project_completed": False,
            "account_id": self.account,
            "envelope_id": self.envelope,
            "completed_at": timezone.now().isoformat(),
            "signers": [],
            "_validated_pdf_bytes": {
                "1": self.pdf,
                "certificate": self.certificate,
            },
            "pdf_manifest": [
                {
                    "document_id": "1",
                    "pdf_sha256": hashlib.sha256(
                        self.pdf
                    ).hexdigest(),
                    "size_bytes": len(self.pdf),
                },
                {
                    "document_id": "certificate",
                    "pdf_sha256": hashlib.sha256(
                        self.certificate
                    ).hexdigest(),
                    "size_bytes": len(self.certificate),
                },
            ],
        }

    def retain(self, *, evidence=None, actor=None, enabled="1"):
        # Approval mocks are confined to this disposable test process.
        with patch.dict(
            "os.environ",
            {"GECC_SANDBOX_COMPLETION_RETENTION_ENABLED": enabled},
        ), patch(
            "core.release.validate_package"
        ), patch(
            "core.release.status",
            return_value={"status": "APPROVED"},
        ):
            return retain_authenticated_completion(
                actor=self.comptroller if actor is None else actor,
                attempt_id=str(self.attempt.pk),
                challenge=self.challenge,
                evidence=self.evidence if evidence is None else evidence,
            )

    def test_new_attempt_starts_in_authorized_pending_state(self):
        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "AUTH_PENDING")
        self.assertIsNone(self.attempt.first_send_started_at)
        self.assertEqual(self.attempt.provider_envelope_id, "")
        self.assertFalse(
            CompletionSignatureVerification.objects.exists()
        )

    def test_disabled_retention_prevents_database_writes(self):
        with self.assertRaises(ValidationError):
            self.retain(enabled="0")
        self.assertFalse(
            CompletionSignatureVerification.objects.exists()
        )
        self.assertFalse(
            CompletionSignatureDocument.objects.exists()
        )

    def test_unsent_attempt_cannot_be_retained(self):
        with self.assertRaises(ValidationError):
            self.retain()
        self.assertFalse(
            CompletionSignatureVerification.objects.exists()
        )
        self.assertFalse(
            CompletionSignatureDocument.objects.exists()
        )

    def test_tampered_pdf_rejected_without_writes(self):
        self.evidence["_validated_pdf_bytes"]["1"] += b"tampered"
        with self.assertRaises(ValidationError):
            self.retain()
        self.assertFalse(
            CompletionSignatureVerification.objects.exists()
        )

    def test_forged_sent_transition_rejected_by_database(self):
        # Never disable or circumvent the lifecycle trigger.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CompletionEnvelopeAttempt.objects.filter(
                    pk=self.attempt.pk
                ).update(
                    state="SENT_UNCHECKED",
                    provider_envelope_id=self.envelope,
                    first_send_started_at=timezone.now(),
                )

        self.attempt.refresh_from_db()
        self.assertEqual(self.attempt.state, "AUTH_PENDING")
        self.assertEqual(self.attempt.provider_envelope_id, "")
        self.assertIsNone(self.attempt.first_send_started_at)

        self.assertFalse(
            CompletionSignatureVerification.objects.exists()
        )
        self.assertFalse(
            CompletionSignatureDocument.objects.exists()
        )
