"""Focused Receipt chain security regressions, no database access."""
import hashlib
from types import SimpleNamespace
from uuid import uuid4

from django.test import SimpleTestCase

from .receipt_evidence_chain_4613 import assess_receipt_chain


class ReceiptEvidenceChainTests(SimpleTestCase):
    def setUp(self):
        self.pid = uuid4()
        self.mid = uuid4()
        self.did = uuid4()
        self.pdf = b"%PDF-1.4\\nfictional document"
        self.digest = hashlib.sha256(self.pdf).hexdigest()
        self.msr = SimpleNamespace(
            pk=self.mid, project_id=self.pid, status="APPROVED",
            snapshot={"customer_email": "customer@example.test"},
        )
        self.project = SimpleNamespace(
            pk=self.pid, state="APPROVED", current_approved=self.msr,
        )
        self.document = SimpleNamespace(
            pk=self.did, msr_id=self.mid, kind="INVOICE",
            status="PREPARATION", content=self.pdf,
            pdf_sha256=self.digest,
        )
        self.outbox = SimpleNamespace(
            project_id=self.pid, msr_id=self.mid,
            document_id=self.did,
            recipient_email="customer@example.test",
            pdf_sha256=self.digest, status="PENDING",
        )
        self.observation = SimpleNamespace(
            msr_id=self.mid, document_id=self.did,
            recipient_email="customer@example.test",
            pdf_sha256=self.digest, status="UNVERIFIED",
        )

    def assess(self):
        return assess_receipt_chain(
            project=self.project,
            documents=[self.document],
            outboxes=[self.outbox],
            observations=[self.observation],
        )

    def test_matches_are_not_completion_authority(self):
        result = self.assess()
        self.assertEqual(
            (result["valid_pdf_candidates"],
             result["matching_outbox_intents"],
             result["matching_local_observations"]),
            (1, 1, 1),
        )
        self.assertFalse(result["final_receipt_verified"])
        self.assertFalse(result["provider_email_authenticated"])
        self.assertFalse(result["completion_authorized"])

    def test_tampered_pdf_rejected(self):
        self.document.content += b"changed"
        self.assertEqual(self.assess()["valid_pdf_candidates"], 0)

    def test_wrong_customer_email_rejected(self):
        self.outbox.recipient_email = "other@example.test"
        self.observation.recipient_email = "other@example.test"
        result = self.assess()
        self.assertEqual(result["matching_outbox_intents"], 0)
        self.assertEqual(result["matching_local_observations"], 0)

    def test_wrong_project_rejected(self):
        self.outbox.project_id = uuid4()
        self.assertEqual(self.assess()["matching_outbox_intents"], 0)

    def test_superseded_msr_rejected(self):
        self.document.msr_id = uuid4()
        self.assertEqual(self.assess()["valid_pdf_candidates"], 0)

    def test_cancelled_project_blocked(self):
        self.project.state = "CANCELLED"
        self.assertEqual(self.assess()["valid_pdf_candidates"], 0)

    def test_forged_observation_state_not_trusted(self):
        self.observation.status = "VERIFIED"
        result = self.assess()
        self.assertEqual(result["matching_local_observations"], 0)
        self.assertFalse(result["provider_email_authenticated"])

    def test_pending_outbox_never_proves_email(self):
        result = self.assess()
        self.assertEqual(result["matching_outbox_intents"], 1)
        self.assertFalse(result["customer_delivery_verified"])
