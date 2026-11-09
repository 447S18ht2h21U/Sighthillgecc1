"""Strict positive and negative candidate evidence bindings."""
from uuid import uuid4
import hashlib

from django.test import SimpleTestCase

from .completion_evidence_binding_preview import (
    assess_completion_evidence_bindings,
)


class CompletionEvidenceBindingTests(SimpleTestCase):
    def setUp(self):
        self.project = str(uuid4())
        self.msr = str(uuid4())
        self.receipt_id = str(uuid4())
        self.certificate_id = str(uuid4())
        self.pdf = b"%PDF-1.4\nreceipt test bytes\n%%EOF"
        self.cert_pdf = b"%PDF-1.4\ncertificate test bytes\n%%EOF"
        self.receipt_sha = hashlib.sha256(self.pdf).hexdigest()
        self.cert_sha = hashlib.sha256(self.cert_pdf).hexdigest()
        common = {"project_id": self.project, "msr_id": self.msr}
        self.receipt = {
            **common, "document_id": self.receipt_id,
            "kind": "RECEIPT", "pdf": self.pdf,
            "pdf_sha256": self.receipt_sha,
        }
        self.email = {
            **common, "document_id": self.receipt_id,
            "pdf_sha256": self.receipt_sha,
            "recipient_email": "customer@example.com",
            "provider_message_id": "provider-msg-123",
            "provider_status": "SENT",
        }
        self.certificate = {
            **common, "document_id": self.certificate_id,
            "kind": "COMPLETION_FINANCED",
            "pdf": self.cert_pdf,
            "pdf_sha256": self.cert_sha,
        }
        self.provider = {
            **common, "document_id": self.certificate_id,
            "pdf_sha256": self.cert_sha,
            "certificate_kind": "COMPLETION_FINANCED",
            "envelope_id": str(uuid4()),
            "provider_account_id": "provider-account",
            "status": "completed",
        }

    def assess(self, **changes):
        data = {
            "project_id": self.project, "msr_id": self.msr,
            "customer_email": "customer@example.com",
            "receipt": self.receipt, "email_evidence": self.email,
            "certificate": self.certificate,
            "provider_evidence": self.provider,
        }
        data.update(changes)
        return assess_completion_evidence_bindings(**data)

    def test_all_candidates_bind_but_no_authority(self):
        r = self.assess()
        self.assertTrue(r.candidate_evidence_complete)
        self.assertFalse(r.evidence_trusted)
        self.assertFalse(r.project_completion_authorized)
        self.assertFalse(r.project_completed)

    def test_receipt_pdf_mismatch_denied(self):
        r = self.assess(receipt={**self.receipt, "pdf": b"%PDF-fake"})
        self.assertFalse(r.receipt_candidate_bound)
        self.assertFalse(r.candidate_evidence_complete)

    def test_email_wrong_customer_denied(self):
        r = self.assess(email_evidence={
            **self.email, "recipient_email": "other@example.com"
        })
        self.assertFalse(r.receipt_candidate_bound)

    def test_email_wrong_document_denied(self):
        r = self.assess(email_evidence={
            **self.email, "document_id": str(uuid4())
        })
        self.assertFalse(r.receipt_candidate_bound)

    def test_unsent_email_denied(self):
        r = self.assess(email_evidence={
            **self.email, "provider_status": "DRAFT"
        })
        self.assertFalse(r.receipt_candidate_bound)

    def test_wrong_project_denied(self):
        r = self.assess(receipt={
            **self.receipt, "project_id": str(uuid4())
        })
        self.assertFalse(r.candidate_evidence_complete)

    def test_wrong_msr_certificate_denied(self):
        r = self.assess(certificate={
            **self.certificate, "msr_id": str(uuid4())
        })
        self.assertFalse(r.certificate_candidate_bound)

    def test_docusign_not_completed_denied(self):
        r = self.assess(provider_evidence={
            **self.provider, "status": "sent"
        })
        self.assertFalse(r.certificate_candidate_bound)

    def test_provider_wrong_envelope_denied(self):
        r = self.assess(provider_evidence={
            **self.provider, "envelope_id": "not-a-uuid"
        })
        self.assertFalse(r.certificate_candidate_bound)

    def test_survey_is_optional(self):
        a = self.assess(satisfaction_survey_received=False)
        b = self.assess(satisfaction_survey_received=True)
        self.assertTrue(a.candidate_evidence_complete)
        self.assertTrue(b.candidate_evidence_complete)
        self.assertFalse(a.project_completion_authorized)
        self.assertFalse(b.project_completion_authorized)