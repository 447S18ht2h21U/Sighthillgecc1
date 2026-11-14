import base64
import hashlib
from unittest import TestCase

from django.core.exceptions import ValidationError

from .receipt_microsoft_graph_preview_4927 import (
    classify_graph_submission,
    prepare_graph_receipt_preview,
)


PDF = b"%PDF-1.4\nsynthetic offline test\n%%EOF\n"


def inputs():
    return {
        "pdf_bytes": PDF,
        "expected_sha256": hashlib.sha256(PDF).hexdigest(),
        "recipient": "synthetic@example.invalid",
        "approved_email": "synthetic@example.invalid",
        "approved_msr_id": "synthetic-msr-4927",
        "document_msr_id": "synthetic-msr-4927",
        "document_kind": "RECEIPT",
        "document_status": "FINAL",
    }


class MicrosoftGraphReceiptPreviewTests(TestCase):

    def test_offline_request_binds_exact_pdf_and_recipient(self):
        result = prepare_graph_receipt_preview(**inputs())
        self.assertEqual(result.status, "PREVIEW_ONLY_NOT_SUBMITTED")
        self.assertFalse(result.submission_accepted)
        self.assertFalse(result.provider_authenticated)
        self.assertFalse(result.customer_delivery_verified)
        self.assertFalse(result.completion_authorized)
        self.assertIn("/users/care%40gecc.cloud/sendMail", result.endpoint)
        self.assertEqual(
            result.request_body["message"]["toRecipients"][0]
            ["emailAddress"]["address"], "synthetic@example.invalid"
        )
        attachment = result.request_body["message"]["attachments"][0]
        self.assertEqual(
            base64.b64decode(attachment["contentBytes"]), PDF
        )

    def test_recipient_mismatch_rejected(self):
        values = inputs()
        values["recipient"] = "other@example.invalid"
        with self.assertRaises(ValidationError):
            prepare_graph_receipt_preview(**values)

    def test_msr_mismatch_rejected(self):
        values = inputs()
        values["document_msr_id"] = "different-msr"
        with self.assertRaises(ValidationError):
            prepare_graph_receipt_preview(**values)

    def test_historical_invoice_rejected(self):
        values = inputs()
        values["document_kind"] = "INVOICE"
        with self.assertRaises(ValidationError):
            prepare_graph_receipt_preview(**values)

    def test_draft_receipt_rejected(self):
        values = inputs()
        values["document_status"] = "PREPARATION"
        with self.assertRaises(ValidationError):
            prepare_graph_receipt_preview(**values)

    def test_fingerprint_mismatch_rejected(self):
        values = inputs()
        values["expected_sha256"] = "0" * 64
        with self.assertRaises(ValidationError):
            prepare_graph_receipt_preview(**values)

    def test_incomplete_pdf_rejected(self):
        values = inputs()
        values["pdf_bytes"] = b"%PDF-1.4\nincomplete"
        values["expected_sha256"] = hashlib.sha256(
            values["pdf_bytes"]
        ).hexdigest()
        with self.assertRaises(ValidationError):
            prepare_graph_receipt_preview(**values)

    def test_live_mode_rejected(self):
        values = inputs()
        values["mode"] = "LIVE"
        with self.assertRaises(ValidationError):
            prepare_graph_receipt_preview(**values)

    def test_graph_202_never_means_delivery(self):
        status = classify_graph_submission(202)
        self.assertEqual(
            status["status"],
            "SUBMISSION_ACCEPTED_DELIVERY_UNVERIFIED",
        )
        self.assertFalse(status["provider_authenticated"])
        self.assertFalse(status["customer_delivery_verified"])
        self.assertFalse(status["completion_authorized"])

    def test_failed_submission_never_means_delivery(self):
        status = classify_graph_submission(403)
        self.assertEqual(status["status"], "SUBMISSION_NOT_ACCEPTED")
        self.assertFalse(status["customer_delivery_verified"])
