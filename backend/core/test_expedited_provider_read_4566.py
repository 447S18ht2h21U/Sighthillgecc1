from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from .expedited_provider_read_4566 import read_expedited_candidate


@override_settings(ENVIRONMENT="development", DEBUG=True)
class ExpeditedProviderRead4566Tests(SimpleTestCase):
    def setUp(self):
        self.account = str(uuid4())
        self.envelope = str(uuid4())
        self.expected = {"envelope_id": self.envelope}
        self.summary = {
            "envelopeId": self.envelope,
            "status": "completed",
            "lastModifiedDateTime": "fictional-stable-marker",
            "completedDateTime": "fictional-completion-marker",
        }
        self.config = {
            "account_id": self.account, "blockers": [],
        }

    def read(self, responses=None):
        if responses is None:
            responses = [
                self.summary,
                {"signers": []},
                {"envelopeDocuments": []},
                dict(self.summary),
            ]
        with patch(
            "core.expedited_provider_read_4566.docusign.configuration",
            return_value=self.config,
        ), patch(
            "core.expedited_provider_read_4566.signing_test.provider",
            side_effect=responses,
        ) as provider, patch(
            "core.expedited_provider_read_4566.signing_test.pdf_document",
            return_value=b"fictional-bytes",
        ) as pdf, patch(
            "core.expedited_provider_read_4566.validate_candidate_expedited_bundle",
            return_value={"status": "STRUCTURALLY_VALID_UNAUTHENTICATED_CANDIDATE"},
        ) as validate:
            result = read_expedited_candidate(
                account_id=self.account,
                envelope_id=self.envelope,
                token="fictional-oauth-token",
                expected=self.expected,
            )
            return result, provider, pdf, validate

    def test_provider_retrieval_and_recheck_remain_untrusted(self):
        result, provider, pdf, validate = self.read()
        self.assertEqual(provider.call_count, 4)
        self.assertEqual(pdf.call_count, 3)
        self.assertEqual(validate.call_count, 1)
        self.assertTrue(result["retrieved_from_sandbox"])
        self.assertFalse(result["provider_authenticated"])
        self.assertFalse(result["customer_initials_verified"])
        self.assertFalse(result["installation_authorized"])

    def test_envelope_changed_during_read_rejected(self):
        changed = dict(self.summary)
        changed["lastModifiedDateTime"] = "different-marker"
        with self.assertRaises(ValidationError):
            self.read([
                self.summary, {"signers": []},
                {"envelopeDocuments": []}, changed,
            ])

    def test_wrong_account_rejected_before_provider_call(self):
        self.config["account_id"] = str(uuid4())
        with self.assertRaises(PermissionDenied):
            self.read()

    def test_wrong_envelope_rejected_before_provider_call(self):
        self.expected["envelope_id"] = str(uuid4())
        with self.assertRaises(ValidationError):
            self.read()

    def test_provider_failure_fails_closed(self):
        with self.assertRaises(ValidationError):
            self.read([ValidationError("Provider unavailable")])

    def test_missing_token_rejected(self):
        with patch(
            "core.expedited_provider_read_4566.docusign.configuration",
            return_value=self.config,
        ):
            with self.assertRaises(ValidationError):
                read_expedited_candidate(
                    account_id=self.account,
                    envelope_id=self.envelope,
                    token="",
                    expected=self.expected,
                )

    @override_settings(ENVIRONMENT="production", DEBUG=False)
    def test_production_disabled(self):
        with self.assertRaises(PermissionDenied):
            read_expedited_candidate(
                account_id=self.account,
                envelope_id=self.envelope,
                token="fictional-token",
                expected=self.expected,
            )
