"""Database-free integrity tests for the completion retention boundary."""
import hashlib
from unittest import TestCase

from rest_framework.exceptions import ValidationError

from .completion_retention_4612 import validated_pdf_bundle


class CompletionRetentionBoundaryTests(TestCase):
    def setUp(self):
        self.document = b"%PDF-1.4\\nexample document"
        self.certificate = b"%PDF-1.4\\nprovider certificate"
        self.evidence = {
            "provider_response_validated": True,
            "completion_authorized": False,
            "project_completed": False,
            "_validated_pdf_bytes": {
                "1": self.document,
                "certificate": self.certificate,
            },
            "pdf_manifest": [
                {
                    "document_id": "1",
                    "pdf_sha256": hashlib.sha256(
                        self.document
                    ).hexdigest(),
                    "size_bytes": len(self.document),
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

    def test_exact_bundle_accepted_without_completion_authority(self):
        result = validated_pdf_bundle(self.evidence)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[1][0], "certificate")
        self.assertFalse(self.evidence["completion_authorized"])

    def test_modified_pdf_denied(self):
        self.evidence["_validated_pdf_bytes"]["1"] += b"modified"
        with self.assertRaises(ValidationError):
            validated_pdf_bundle(self.evidence)

    def test_missing_provider_certificate_denied(self):
        self.evidence["pdf_manifest"].pop()
        with self.assertRaises(ValidationError):
            validated_pdf_bundle(self.evidence)

    def test_forged_completion_authority_denied(self):
        self.evidence["completion_authorized"] = True
        with self.assertRaises(ValidationError):
            validated_pdf_bundle(self.evidence)

    def test_provider_credentials_must_not_be_retained(self):
        self.evidence["access_token"] = "forbidden"
        with self.assertRaises(ValidationError):
            validated_pdf_bundle(self.evidence)
