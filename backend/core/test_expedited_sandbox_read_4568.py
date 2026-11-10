
from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from .expedited_sandbox_read_4568 import read_unified_sandbox_candidate

MODULE = "core.expedited_sandbox_read_4568"


@override_settings(ENVIRONMENT="development", DEBUG=True)
class UnifiedSandboxRead4568Tests(SimpleTestCase):
    def setUp(self):
        self.account = str(uuid4())
        self.envelope = str(uuid4())
        self.token = "fictional-token-not-a-real-secret"
        self.offline = {"status": "UNSENDABLE_OFFLINE_CANDIDATE"}
        self.summary = {
            "envelopeId": self.envelope,
            "status": "completed",
            "completedDateTime": "2026-11-15T18:00:00Z",
            "lastModifiedDateTime": "2026-11-15T18:00:00Z",
        }
        self.result = {
            "status": "THREE_DOCUMENT_STRUCTURAL_CANDIDATE_ONLY",
            "envelope_id": self.envelope,
            "source_msr_id": str(uuid4()),
            "retrieved_document_hashes": {
                "1": "a" * 64,
                "2": "b" * 64,
                "certificate": "c" * 64,
            },
            "manager_candidate_decision": "APPROVED",
            "comptroller_candidate_decision": "APPROVED",
            "provider_authenticated": False,
            "installation_authorized": False,
        }
        self.config = {"account_id": self.account, "blockers": []}
        self.second = None

    def check(self):
        def provider(account, envelope, token, resource=""):
            self.assertEqual(account, self.account)
            self.assertEqual(envelope, self.envelope)
            self.assertEqual(token, self.token)
            if resource == "":
                provider.reads += 1
                return deepcopy(
                    self.second if provider.reads == 2
                    and self.second is not None else self.summary
                )
            if resource == "/recipients?include_tabs=true":
                return {"signers": []}
            if resource == "/documents":
                return {"envelopeDocuments": []}
            raise AssertionError("Unexpected provider resource")

        provider.reads = 0
        with (
            patch(f"{MODULE}.docusign.configuration",
                  return_value=self.config),
            patch(f"{MODULE}.validate_offline_tab_contract",
                  return_value={
                      "status": "OFFLINE_TAB_CONTRACT_VALIDATED",
                      "provider_behavior_verified": False,
                      "send_authorized": False,
                      "installation_authorized": False,
                  }),
            patch(f"{MODULE}.signing_test.provider",
                  side_effect=provider) as read,
            patch(f"{MODULE}.signing_test.pdf_document",
                  return_value=b"%PDF-fictional") as pdf,
            patch(f"{MODULE}.validate_retention_candidate",
                  return_value=self.result) as validate,
        ):
            output = read_unified_sandbox_candidate(
                account_id=self.account,
                envelope_id=self.envelope,
                token=self.token,
                offline_envelope=self.offline,
            )
            self.assertEqual(read.call_count, 4)
            self.assertEqual(pdf.call_count, 3)
            validate.assert_called_once()
            return output

    def test_stable_three_document_read_remains_untrusted(self):
        result = self.check()
        self.assertEqual(
            set(result["document_hashes"]),
            {"1", "2", "certificate"}
        )
        self.assertFalse(result["provider_authenticated"])
        self.assertFalse(result["installation_authorized"])
        self.assertFalse(result["send_authorized"])
        self.assertNotIn("token", result)
        self.assertNotIn("signed_pdfs", result)

    def test_changed_envelope_after_read_fails(self):
        self.second = {
            **self.summary,
            "lastModifiedDateTime": "2026-11-15T18:01:00Z",
        }
        with self.assertRaises(ValidationError):
            self.check()

    def test_changed_completion_status_fails(self):
        self.second = {**self.summary, "status": "voided"}
        with self.assertRaises(ValidationError):
            self.check()

    def test_wrong_account_rejected_before_read(self):
        with self.assertRaises(PermissionDenied):
            read_unified_sandbox_candidate(
                account_id=str(uuid4()),
                envelope_id=self.envelope,
                token=self.token,
                offline_envelope=self.offline,
            )

    def test_missing_token_rejected(self):
        with patch(
            f"{MODULE}.docusign.configuration",
            return_value=self.config,
        ):
            with self.assertRaises(ValidationError):
                read_unified_sandbox_candidate(
                    account_id=self.account,
                    envelope_id=self.envelope,
                    token="",
                    offline_envelope=self.offline,
                )

    def test_incomplete_envelope_rejected(self):
        self.summary["status"] = "sent"
        with self.assertRaises(ValidationError):
            self.check()

    def test_retention_approval_claim_rejected(self):
        self.result["provider_authenticated"] = True
        with self.assertRaises(ValidationError):
            self.check()

    def test_retention_missing_certificate_rejected(self):
        del self.result["retrieved_document_hashes"]["certificate"]
        with self.assertRaises(ValidationError):
            self.check()

    def test_provider_adapter_error_propagates(self):
        with (
            patch(f"{MODULE}.docusign.configuration",
                  return_value=self.config),
            patch(f"{MODULE}.validate_offline_tab_contract",
                  return_value={
                      "status": "OFFLINE_TAB_CONTRACT_VALIDATED",
                      "provider_behavior_verified": False,
                      "send_authorized": False,
                      "installation_authorized": False,
                  }),
            patch(
                f"{MODULE}.signing_test.provider",
                side_effect=ValidationError("Provider read failed"),
            ),
        ):
            with self.assertRaises(ValidationError):
                read_unified_sandbox_candidate(
                    account_id=self.account,
                    envelope_id=self.envelope,
                    token=self.token,
                    offline_envelope=self.offline,
                )

    @override_settings(ENVIRONMENT="production", DEBUG=False)
    def test_production_disabled(self):
        with self.assertRaises(PermissionDenied):
            read_unified_sandbox_candidate(
                account_id=self.account,
                envelope_id=self.envelope,
                token=self.token,
                offline_envelope=self.offline,
            )
