
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from .expedited_retention_evidence_4568 import (
    validate_retention_candidate,
)

MODULE = "core.expedited_retention_evidence_4568"


@override_settings(ENVIRONMENT="development", DEBUG=True)
class ExpeditedRetention4568Tests(SimpleTestCase):
    def setUp(self):
        self.eid = str(uuid4())
        root = (
            Path(__file__).resolve().parents[2]
            / "docs/reference/GECC-20261107-final-seven"
        )
        first = "GECC Project Scope of Work 20261107v2.pdf"
        second = "GECC Expedite Service Request 20261107v2.pdf"

        self.offline = {
            "source_msr_id": str(uuid4()),
            "documents": [
                {"documentId": "1", "name": first},
                {"documentId": "2", "name": second},
            ],
        }
        self.summary = {
            "envelopeId": self.eid,
            "status": "completed",
        }
        self.recipients = {"signers": []}
        self.documents = {
            "envelopeDocuments": [
                {"documentId": "1", "name": first},
                {"documentId": "2", "name": second},
                {
                    "documentId": "certificate",
                    "name": "Certificate of Completion",
                },
            ],
        }
        self.pdfs = {
            "1": (root / first).read_bytes(),
            "2": (root / second).read_bytes(),
            # Fictional test fixture only, NOT an actual certificate.
            "certificate": (root / second).read_bytes(),
        }
        self.structural = {
            "status": "THREE_SIGNER_STRUCTURAL_CANDIDATE_ONLY",
            "envelope_id": self.eid,
            "manager_candidate_decision": "APPROVED",
            "comptroller_candidate_decision": "APPROVED",
            "provider_authenticated": False,
            "installation_authorized": False,
        }

    def check(self):
        with patch(
            f"{MODULE}.validate_three_signer_observation",
            return_value=self.structural,
        ) as validator:
            result = validate_retention_candidate(
                expected_envelope_id=self.eid,
                offline_envelope=self.offline,
                summary=self.summary,
                recipients=self.recipients,
                documents=self.documents,
                signed_pdfs=self.pdfs,
            )
            validator.assert_called_once()
            return result

    def test_complete_fictional_bundle_remains_untrusted(self):
        result = self.check()
        self.assertEqual(
            set(result["retrieved_document_hashes"]),
            {"1", "2", "certificate"},
        )
        self.assertFalse(result["provider_authenticated"])
        self.assertFalse(result["durably_retained"])
        self.assertFalse(result["installation_authorized"])

    def test_missing_certificate_rejected(self):
        del self.pdfs["certificate"]
        with self.assertRaises(ValidationError):
            self.check()

    def test_missing_document_metadata_rejected(self):
        self.documents["envelopeDocuments"].pop()
        with self.assertRaises(ValidationError):
            self.check()

    def test_duplicate_document_id_rejected(self):
        self.documents["envelopeDocuments"][1]["documentId"] = "1"
        with self.assertRaises(ValidationError):
            self.check()

    def test_changed_document_name_rejected(self):
        self.documents["envelopeDocuments"][0]["name"] = "Other.pdf"
        with self.assertRaises(ValidationError):
            self.check()

    def test_invalid_pdf_bytes_rejected(self):
        self.pdfs["2"] = b"not a PDF"
        with self.assertRaises(ValidationError):
            self.check()

    def test_mismatched_envelope_rejected(self):
        self.structural["envelope_id"] = str(uuid4())
        with self.assertRaises(ValidationError):
            self.check()

    def test_authenticated_claim_rejected(self):
        self.structural["provider_authenticated"] = True
        with self.assertRaises(ValidationError):
            self.check()

    def test_rejection_does_not_grant_installation(self):
        self.structural["manager_candidate_decision"] = "REJECTED"
        result = self.check()
        self.assertEqual(
            result["manager_candidate_decision"], "REJECTED",
        )
        self.assertFalse(result["expedited_authorized"])
        self.assertFalse(result["installation_authorized"])

    @override_settings(ENVIRONMENT="production", DEBUG=False)
    def test_production_disabled(self):
        with self.assertRaises(PermissionDenied):
            self.check()
