import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.test import SimpleTestCase

from .commercial_signature_preflight_5532 import (
    assess_commercial_evidence,
)


class CommercialSignaturePreflightTests(SimpleTestCase):
    def setUp(self):
        self.msr = str(uuid4())
        self.account = str(uuid4())
        self.envelope = str(uuid4())
        self.signed = b"%PDF-1.4\\nfictional fixture"
        self.certificate = b"%PDF-1.4\\nfictional certificate"
        self.signed_at = datetime.now(timezone.utc) - timedelta(hours=2)
        self.completed_at = self.signed_at + timedelta(minutes=10)

        self.data = {
            "expected_msr_id": self.msr,
            "expected_kind": "CONTRACT",
            "expected_customer_email": "customer@example.test",
            "account_id": self.account,
            "envelope_id": self.envelope,
            "provider_summary": {
                "envelopeId": self.envelope,
                "status": "completed",
                "completed_at": self.completed_at,
            },
            "expected_release_binding": {
                "msr_id": self.msr,
                "document_kind": "CONTRACT",
                "account_id": self.account,
                "envelope_id": self.envelope,
            },
            "provider_signers": [{
                "recipientId": "1",
                "email": "customer@example.test",
                "status": "completed",
                "signed_at": self.signed_at,
            }],
            "signed_pdf": self.signed,
            "certificate_pdf": self.certificate,
            "retained_signed_sha256":
                hashlib.sha256(self.signed).hexdigest(),
            "retained_certificate_sha256":
                hashlib.sha256(self.certificate).hexdigest(),
        }

    def assess(self, **changes):
        return assess_commercial_evidence(**(self.data | changes))

    def test_matching_evidence_does_not_authorize(self):
        result = self.assess()
        self.assertTrue(result["correlation_passed"])
        self.assertFalse(result["signature_authenticated"])
        self.assertFalse(result["installation_authorized"])

    def test_wrong_envelope_rejected(self):
        result = self.assess(provider_summary={
            **self.data["provider_summary"],
            "envelopeId": str(uuid4()),
        })
        self.assertFalse(result["correlation_passed"])

    def test_wrong_customer_rejected(self):
        result = self.assess(expected_customer_email="other@example.test")
        self.assertFalse(result["correlation_passed"])

    def test_wrong_document_digest_rejected(self):
        result = self.assess(retained_signed_sha256="0" * 64)
        self.assertFalse(result["correlation_passed"])

    def test_uncompleted_envelope_rejected(self):
        result = self.assess(provider_summary={
            **self.data["provider_summary"],
            "status": "sent",
        })
        self.assertFalse(result["correlation_passed"])

    def test_future_signature_rejected(self):
        result = self.assess(provider_signers=[{
            **self.data["provider_signers"][0],
            "signed_at": datetime.now(timezone.utc) + timedelta(days=1),
        }])
        self.assertFalse(result["correlation_passed"])

    def test_invoice_requires_same_controls(self):
        result = self.assess(
            expected_kind="INVOICE",
            expected_release_binding={
                **self.data["expected_release_binding"],
                "document_kind": "INVOICE",
            },
        )
        self.assertTrue(result["correlation_passed"])
        self.assertFalse(result["signature_authenticated"])

    def test_missing_release_binding_rejected(self):
        result = self.assess(expected_release_binding=None)
        self.assertFalse(result["correlation_passed"])

    def test_wrong_msr_binding_rejected(self):
        binding = {
            **self.data["expected_release_binding"],
            "msr_id": str(uuid4()),
        }
        result = self.assess(expected_release_binding=binding)
        self.assertFalse(result["correlation_passed"])

    def test_wrong_document_binding_rejected(self):
        binding = {
            **self.data["expected_release_binding"],
            "document_kind": "INVOICE",
        }
        result = self.assess(expected_release_binding=binding)
        self.assertFalse(result["correlation_passed"])

    def test_wrong_account_binding_rejected(self):
        binding = {
            **self.data["expected_release_binding"],
            "account_id": str(uuid4()),
        }
        result = self.assess(expected_release_binding=binding)
        self.assertFalse(result["correlation_passed"])

    def test_duplicate_signers_rejected(self):
        signer = self.data["provider_signers"][0]
        result = self.assess(provider_signers=[signer, signer])
        self.assertFalse(result["correlation_passed"])

    def test_future_customer_signature_rejected(self):
        signer = {
            **self.data["provider_signers"][0],
            "signed_at": datetime.now(timezone.utc) + timedelta(days=2),
        }
        summary = {
            **self.data["provider_summary"],
            "completed_at": datetime.now(timezone.utc) + timedelta(days=3),
        }
        result = self.assess(
            provider_signers=[signer],
            provider_summary=summary,
        )
        self.assertFalse(result["correlation_passed"])
