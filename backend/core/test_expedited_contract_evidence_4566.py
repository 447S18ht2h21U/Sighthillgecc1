from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase
from django.utils import timezone

from .documents import canonical_hash
from .expedited_contract_evidence_4566 import (
    ContractEvidenceAssessment, assess_contract_evidence,
)
from .installation_start_control_4565 import assess_installation_start


class ContractEvidence4566Tests(SimpleTestCase):

    def setUp(self):
        project_id = uuid4()
        self.msr = SimpleNamespace(
            pk=uuid4(),
            project_id=project_id,
            status="APPROVED",
            snapshot={"fictional": "contract"},
        )
        self.project = SimpleNamespace(
            pk=project_id,
            current_approved=self.msr,
        )
        content = b"%PDF-1.4 fictional-only content"
        self.document = SimpleNamespace(
            content=content,
            snapshot_sha256=canonical_hash(self.msr.snapshot),
            pdf_sha256=sha256(content).hexdigest(),
        )

    def assess(self, document, customer_signed=True):
        with patch(
            "core.expedited_contract_evidence_4566."
            "CustomerSignatureEvidence.objects.filter"
        ) as signatures, patch(
            "core.expedited_contract_evidence_4566.Document.objects.filter"
        ) as documents:
            signatures.return_value.exists.return_value = customer_signed
            documents.return_value.order_by.return_value.first.return_value = document
            result = assess_contract_evidence(self.project)
        return result

    def test_intact_generated_document_is_not_customer_initials(self):
        result = self.assess(self.document)
        self.assertTrue(result.customer_contract_signature_recorded)
        self.assertTrue(result.generated_contract_integrity_verified)
        self.assertFalse(result.customer_initials_verified)
        self.assertFalse(result.signed_expedited_document_verified)
        self.assertFalse(result.installation_authorized)

    def test_modified_pdf_is_rejected(self):
        document = SimpleNamespace(
            content=self.document.content + b" altered",
            snapshot_sha256=self.document.snapshot_sha256,
            pdf_sha256=self.document.pdf_sha256,
        )
        result = self.assess(document)
        self.assertFalse(result.generated_contract_integrity_verified)

    def test_wrong_msr_snapshot_is_rejected(self):
        document = SimpleNamespace(
            content=self.document.content,
            snapshot_sha256="0" * 64,
            pdf_sha256=self.document.pdf_sha256,
        )
        result = self.assess(document)
        self.assertFalse(result.generated_contract_integrity_verified)

    def test_missing_customer_signature_is_reported_separately(self):
        result = self.assess(self.document, customer_signed=False)
        self.assertFalse(result.customer_contract_signature_recorded)
        self.assertTrue(result.generated_contract_integrity_verified)
        self.assertFalse(result.installation_authorized)

    def test_unapproved_msr_fails_closed_without_query(self):
        self.msr.status = "DRAFT"
        with patch(
            "core.expedited_contract_evidence_4566.Document.objects.filter"
        ) as documents:
            result = assess_contract_evidence(self.project)
        documents.assert_not_called()
        self.assertFalse(result.generated_contract_integrity_verified)

    def test_start_assessment_reports_evidence_without_authorizing(self):
        schedule = SimpleNamespace(schedule_verified=True, blockers=())
        contract = ContractEvidenceAssessment(
            customer_contract_signature_recorded=True,
            generated_contract_integrity_verified=True,
        )
        with patch(
            "core.installation_start_control_4565.assess_database_schedule",
            return_value=schedule,
        ), patch(
            "core.installation_start_control_4565.ensure_installation_eligible",
            return_value=True,
        ), patch(
            "core.installation_start_control_4565.assess_contract_evidence",
            return_value=contract,
        ):
            result = assess_installation_start(
                project=self.project,
                proposed_start=timezone.now(),
            )
        self.assertTrue(result["customer_contract_signature_recorded"])
        self.assertTrue(result["generated_contract_integrity_verified"])
        self.assertFalse(result["customer_initials_verified"])
        self.assertFalse(result["signed_expedited_document_verified"])
        self.assertFalse(result["installation_authorized"])
        self.assertFalse(result["installation_started"])
