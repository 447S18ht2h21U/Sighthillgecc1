from datetime import timedelta
from io import BytesIO
from uuid import uuid4

from django.test import SimpleTestCase
from django.utils import timezone
from pypdf import PdfWriter
from rest_framework.exceptions import ValidationError

from .expedited_customer_document_validation_4566 import (
    validate_candidate_expedited_bundle,
)


def fictional_pdf():
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.write(output)
    return output.getvalue()


class ExpeditedCustomerDocumentValidation4566Tests(SimpleTestCase):
    def setUp(self):
        now = timezone.now()
        signed = (now - timedelta(minutes=10)).isoformat()
        completed = (now - timedelta(minutes=5)).isoformat()
        self.expected = {
            "envelope_id": str(uuid4()),
            "msr_id": str(uuid4()),
            "msr_version": 3,
            "snapshot_sha256": "a" * 64,
            "proposed_date": (now + timedelta(days=3)).date().isoformat(),
            "customer_name": "Fictional Customer",
            "customer_email": "fictional@example.invalid",
        }
        self.summary = {
            "envelopeId": self.expected["envelope_id"],
            "status": "completed",
            "completedDateTime": completed,
        }
        self.recipients = {
            "signers": [{
                "name": self.expected["customer_name"],
                "email": self.expected["customer_email"],
                "status": "completed",
                "signedDateTime": signed,
                "tabs": {"initialHereTabs": [{
                    "documentId": "1",
                    "tabLabel": "proposed-install-date-initials",
                    "pageNumber": "1",
                    "optional": "false",
                    "xPosition": "120",
                    "yPosition": "200",
                }],
                "textTabs": [{
                    "documentId": "1",
                    "tabLabel": "proposed-install-date",
                    "value": self.expected["proposed_date"],
                    "pageNumber": "1",
                    "xPosition": "100",
                    "yPosition": "200",
                    "optional": "false",
                }],
                "signHereTabs": [{
                    "documentId": "2",
                    "tabLabel": "expedited-service-customer-signature",
                    "pageNumber": "1",
                    "optional": "false",
                }]},
            }],
        }
        self.documents = {
            "envelopeDocuments": [
                {"documentId": "1", "name": "PROJECT_SOW"},
                {"documentId": "2", "name": "REQUEST_FOR_EXPEDITED_SERVICE"},
            ],
        }
        self.pdfs = {
            "1": fictional_pdf(),
            "2": fictional_pdf(),
            "certificate": fictional_pdf(),
        }

    def validate(self):
        return validate_candidate_expedited_bundle(
            expected=self.expected,
            summary=self.summary,
            recipients=self.recipients,
            documents=self.documents,
            signed_pdfs=self.pdfs,
        )

    def test_complete_candidate_remains_untrusted(self):
        result = self.validate()
        self.assertEqual(len(result["retained_document_hashes"]), 3)
        self.assertFalse(result["provider_authenticated"])
        self.assertFalse(result["customer_initials_verified"])
        self.assertFalse(result["installation_authorized"])

    def test_incomplete_envelope_rejected(self):
        self.summary["status"] = "sent"
        with self.assertRaises(ValidationError):
            self.validate()

    def test_wrong_customer_rejected(self):
        self.recipients["signers"][0]["email"] = "other@example.invalid"
        with self.assertRaises(ValidationError):
            self.validate()

    def test_missing_initials_rejected(self):
        self.recipients["signers"][0]["tabs"]["initialHereTabs"] = []
        with self.assertRaises(ValidationError):
            self.validate()

    def test_initials_on_wrong_document_rejected(self):
        tab = self.recipients["signers"][0]["tabs"]["initialHereTabs"][0]
        tab["documentId"] = "2"
        with self.assertRaises(ValidationError):
            self.validate()

    def test_missing_expedited_document_rejected(self):
        self.documents["envelopeDocuments"].pop()
        with self.assertRaises(ValidationError):
            self.validate()

    def test_missing_certificate_rejected(self):
        del self.pdfs["certificate"]
        with self.assertRaises(ValidationError):
            self.validate()

    def test_invalid_pdf_rejected(self):
        self.pdfs["1"] = b"%PDF-not-valid"
        with self.assertRaises(ValidationError):
            self.validate()

    def test_wrong_envelope_rejected(self):
        self.summary["envelopeId"] = str(uuid4())
        with self.assertRaises(ValidationError):
            self.validate()

    def test_future_signature_rejected(self):
        self.recipients["signers"][0]["signedDateTime"] = (
            timezone.now() + timedelta(days=1)
        ).isoformat()
        with self.assertRaises(ValidationError):
            self.validate()

    def test_signature_after_completion_rejected(self):
        self.recipients["signers"][0]["signedDateTime"] = (
            timezone.now() - timedelta(minutes=1)
        ).isoformat()
        with self.assertRaises(ValidationError):
            self.validate()

    def test_proposed_date_mismatch_rejected(self):
        self.recipients["signers"][0]["tabs"]["textTabs"][0][
            "value"
        ] = "2027-01-01"
        with self.assertRaises(ValidationError):
            self.validate()

    def test_initials_not_adjacent_rejected(self):
        self.recipients["signers"][0]["tabs"]["initialHereTabs"][0][
            "xPosition"
        ] = "900"
        with self.assertRaises(ValidationError):
            self.validate()

    def test_missing_expedited_signature_rejected(self):
        self.recipients["signers"][0]["tabs"]["signHereTabs"] = []
        with self.assertRaises(ValidationError):
            self.validate()

    def test_signature_on_wrong_document_rejected(self):
        self.recipients["signers"][0]["tabs"]["signHereTabs"][0][
            "documentId"
        ] = "1"
        with self.assertRaises(ValidationError):
            self.validate()

    def test_optional_expedited_signature_rejected(self):
        self.recipients["signers"][0]["tabs"]["signHereTabs"][0][
            "optional"
        ] = "true"
        with self.assertRaises(ValidationError):
            self.validate()

    def test_missing_proposed_date_rejected(self):
        del self.recipients["signers"][0]["tabs"]["textTabs"][0]["value"]
        with self.assertRaises(ValidationError):
            self.validate()
