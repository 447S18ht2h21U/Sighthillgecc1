"""Synthetic regression tests for pure completion-envelope validation."""

from datetime import timedelta
from django.test import SimpleTestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .completion_signature_validation import validate_completed_envelope, verified_timestamp


class CompletionSignatureValidationTests(SimpleTestCase):
    def test_valid_completed_envelope(self):
        stamp = (timezone.now() - timedelta(minutes=5)).isoformat()
        result = validate_completed_envelope("expected-envelope", {
            "envelopeId": "expected-envelope",
            "status": "completed",
            "completedDateTime": stamp,
        })
        self.assertEqual(result["envelope_id"], "expected-envelope")
        self.assertEqual(result["completed_at"], stamp)

    def test_wrong_envelope_or_incomplete_status_rejected(self):
        stamp = (timezone.now() - timedelta(minutes=5)).isoformat()
        for summary in (None, {},
                        {"envelopeId": "wrong", "status": "completed", "completedDateTime": stamp},
                        {"envelopeId": "expected-envelope", "status": "sent", "completedDateTime": stamp}):
            with self.subTest(summary=summary), self.assertRaises(ValidationError):
                validate_completed_envelope("expected-envelope", summary)

    def test_invalid_timestamps_rejected(self):
        values = (None, "", "not-a-date", "2026-02-30T12:00:00Z",
                  "2020-01-01T12:00:00",
                  (timezone.now() + timedelta(days=1)).isoformat())
        for value in values:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                verified_timestamp(value)

    def test_valid_utc_timestamp(self):
        self.assertIsNotNone(verified_timestamp("2020-01-01T00:00:00Z"))

    def test_completed_signers_valid(self):
        from .completion_signature_validation import validate_completed_signers
        completed = "2020-01-01T12:00:00Z"
        expected = {"recipients": {"signers": [
            {"recipientId": "1", "routingOrder": "2", "name": "Customer", "email": "customer@example.test"},
            {"recipientId": "2", "routingOrder": "1", "name": "GECC", "email": "gecc@example.test"},
        ]}}
        actual = {"signers": [
            {**expected["recipients"]["signers"][0], "status": "completed", "signedDateTime": "2020-01-01T11:30:00Z"},
            {**expected["recipients"]["signers"][1], "status": "completed", "signedDateTime": "2020-01-01T11:00:00Z"},
        ]}
        result = validate_completed_signers(expected, actual, completed)
        self.assertEqual({item["recipient_id"] for item in result}, {"1", "2"})

    def test_completed_signers_reject_invalid_evidence(self):
        import copy
        from .completion_signature_validation import validate_completed_signers
        expected = {"recipients": {"signers": [
            {"recipientId": "1", "routingOrder": "2", "name": "Customer", "email": "customer@example.test"},
            {"recipientId": "2", "routingOrder": "1", "name": "GECC", "email": "gecc@example.test"},
        ]}}
        actual = {"signers": [
            {**expected["recipients"]["signers"][0], "status": "completed", "signedDateTime": "2020-01-01T11:30:00Z"},
            {**expected["recipients"]["signers"][1], "status": "completed", "signedDateTime": "2020-01-01T11:00:00Z"},
        ]}
        for change in ("wrong_email", "incomplete", "wrong_routing", "future_signing", "missing_signer"):
            with self.subTest(change=change):
                planned = copy.deepcopy(expected)
                observed = copy.deepcopy(actual)
                if change == "wrong_email": observed["signers"][0]["email"] = "wrong@example.test"
                elif change == "incomplete": observed["signers"][1]["status"] = "sent"
                elif change == "wrong_routing": planned["recipients"]["signers"][1]["routingOrder"] = "2"
                elif change == "future_signing": observed["signers"][0]["signedDateTime"] = "2020-01-01T13:00:00Z"
                else: observed["signers"].pop()
                with self.assertRaises(ValidationError):
                    validate_completed_signers(planned, observed, "2020-01-01T12:00:00Z")

    def test_customer_cannot_sign_before_gecc(self):
        from .completion_signature_validation import validate_completed_signers
        expected = {"recipients": {"signers": [
            {"recipientId": "1", "routingOrder": "2", "name": "Customer", "email": "customer@example.test"},
            {"recipientId": "2", "routingOrder": "1", "name": "GECC", "email": "gecc@example.test"},
        ]}}
        actual = {"signers": [
            {**expected["recipients"]["signers"][0], "status": "completed", "signedDateTime": "2020-01-01T10:00:00Z"},
            {**expected["recipients"]["signers"][1], "status": "completed", "signedDateTime": "2020-01-01T11:00:00Z"},
        ]}
        with self.assertRaises(ValidationError):
            validate_completed_signers(expected, actual, "2020-01-01T12:00:00Z")

    def test_signature_tab_metadata(self):
        import copy
        from .completion_signature_validation import validate_signature_tabs
        def signer(recipient_id, label):
            return {"recipientId": recipient_id, "tabs": {"signHereTabs": [
                {"documentId": "1", "pageNumber": "1", "xPosition": "100", "yPosition": "200", "tabLabel": label, "optional": "false"}
            ]}}
        expected = {"recipients": {"signers": [signer("1", "customer_signature"), signer("2", "gecc_signature")]}}
        actual = copy.deepcopy(expected["recipients"])
        self.assertTrue(validate_signature_tabs(expected, actual))
        for change in ("missing", "position", "optional", "extra", "duplicate"):
            with self.subTest(change=change):
                altered = copy.deepcopy(actual)
                tabs = altered["signers"][0]["tabs"]
                if change == "missing": tabs["signHereTabs"] = []
                elif change == "position": tabs["signHereTabs"][0]["xPosition"] = "999"
                elif change == "optional": tabs["signHereTabs"][0]["optional"] = "true"
                elif change == "extra": tabs["initialHereTabs"] = [{"tabLabel": "unexpected"}]
                else: tabs["signHereTabs"].append(copy.deepcopy(tabs["signHereTabs"][0]))
                with self.assertRaises(ValidationError):
                    validate_signature_tabs(expected, altered)

    def test_completion_document_identity(self):
        import copy
        from .completion_signature_validation import validate_completion_documents
        expected = {"documents": [
            {"documentId": "1", "name": "completion.pdf"},
            {"documentId": "2", "name": "supporting.pdf"},
        ]}
        observed = {"envelopeDocuments": [
            {"documentId": "1", "name": "completion.pdf"},
            {"documentId": "2", "name": "supporting.pdf"},
            {"documentId": "certificate", "name": "Certificate of Completion"},
        ]}
        result = validate_completion_documents(expected, observed)
        self.assertEqual([item["document_id"] for item in result], ["1", "2"])
        for change in ("missing", "filename", "unexpected", "duplicate", "duplicate_certificate", "malformed"):
            with self.subTest(change=change):
                altered = copy.deepcopy(observed)
                docs = altered["envelopeDocuments"]
                if change == "missing": docs.pop(1)
                elif change == "filename": docs[0]["name"] = "substituted.pdf"
                elif change == "unexpected": docs.append({"documentId": "3", "name": "extra.pdf"})
                elif change == "duplicate": docs[1]["documentId"] = "1"
                elif change == "duplicate_certificate": docs.append(copy.deepcopy(docs[2]))
                else: docs[0] = None
                with self.assertRaises(ValidationError):
                    validate_completion_documents(expected, altered)

    def test_malformed_recipient_metadata_rejected(self):
        from .completion_signature_validation import validate_completed_signers, validate_signature_tabs
        cases = [
            ("signers_null", lambda: validate_completed_signers({"recipients": None}, {"signers": []}, "2020-01-01T00:00:00Z")),
            ("signers_bad_entry", lambda: validate_completed_signers({"recipients": {"signers": [None, None]}}, {"signers": [{}, {}]}, "2020-01-01T00:00:00Z")),
            ("tabs_null", lambda: validate_signature_tabs({"recipients": None}, {"signers": []})),
            ("tabs_bad_entry", lambda: validate_signature_tabs({"recipients": {"signers": [None, None]}}, {"signers": [{}, {}]})),
        ]
        for name, check in cases:
            with self.subTest(case=name), self.assertRaises(ValidationError):
                check()

    def test_signed_pdf_bundle_integrity(self):
        import hashlib
        from io import BytesIO
        from pypdf import PdfWriter
        from .completion_signature_validation import validate_signed_pdf_bundle
        buffer = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.write(buffer)
        pdf = buffer.getvalue()
        documents = {"1": pdf, "2": pdf, "certificate": pdf}
        result = validate_signed_pdf_bundle(["1", "2"], documents)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["pdf_sha256"], hashlib.sha256(pdf).hexdigest())
        self.assertEqual(result[-1]["document_id"], "certificate")
        cases = [
            ("missing_certificate", ["1", "2"], {"1": pdf, "2": pdf}),
            ("unexpected_document", ["1"], documents),
            ("duplicate_expected_id", ["1", "1"], {"1": pdf, "certificate": pdf}),
            ("invalid_pdf", ["1"], {"1": b"not a PDF", "certificate": pdf}),
            ("malformed_pdf", ["1"], {"1": b"%PDF-broken", "certificate": pdf}),
            ("oversized_pdf", ["1"], {"1": pdf + b"x" * (8 * 1024 * 1024), "certificate": pdf}),
        ]
        for name, expected_ids, supplied in cases:
            with self.subTest(case=name), self.assertRaises(ValidationError):
                validate_signed_pdf_bundle(expected_ids, supplied)
