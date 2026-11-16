from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied
from .models import Role
from .installation_provider_readback_4972 import (
    retrieve_inspection_sandbox_evidence,
)
M = "core.installation_provider_readback_4972"
ACCOUNT = "11111111-1111-4111-8111-111111111111"
ENVELOPE = "22222222-2222-4222-8222-222222222222"
PDF = b"%PDF-1.4\n" + b"X" * 200


def reader(path, token, *, pdf=False):
    if pdf:
        return PDF + (b"A" if path.endswith("/1") else b"B")
    if path.endswith("/audit_events"):
        return {
            "auditEvents": [{
                "eventFields": [
                    {"name": "Action", "value": "SyntheticTest"}
                ]
            }]
        }
    if path.endswith("/recipients/1/tabs"):
        return {"radioGroupTabs": []}
    if path.endswith("/recipients"):
        return {"signers": []}
    return {"envelopeId": ENVELOPE, "status": "completed"}


def execute(**changes):
    params = dict(
        actor=SimpleNamespace(is_active=True, role=Role.COMPTROLLER),
        account_id=ACCOUNT, envelope_id=ENVELOPE,
        bearer_token="sandbox-mock-token-never-used", reader=reader,
    )
    params.update(changes)
    with (
        patch(M + ".settings") as settings,
        patch(M + ".os.environ", {"GECC_IM_PROVIDER_READBACK_ENABLED": "1"}),
        patch(M + ".docusign.configuration",
              return_value={"account_id": ACCOUNT, "blockers": []}),
    ):
        settings.ENVIRONMENT = "development"
        settings.DEBUG = True
        return retrieve_inspection_sandbox_evidence(**params)


class SandboxReadback4972Tests(TestCase):
    def test_complete_provider_shaped_readback(self):
        result = execute()
        self.assertEqual(result.envelope_id, ENVELOPE)
        self.assertEqual(result.envelope_summary["status"], "completed")
        self.assertNotEqual(result.signed_pdf_sha256, result.certificate_sha256)
        self.assertFalse(result.signer_identity_verified)
        self.assertFalse(result.provider_signature_verified)
        self.assertFalse(result.completion_authorized)

    def test_invalid_account_rejected(self):
        with self.assertRaises(ValidationError):
            execute(account_id="invalid")

    def test_wrong_account_rejected(self):
        with self.assertRaises(PermissionDenied):
            execute(account_id=ENVELOPE)

    def test_unauthorized_role_rejected(self):
        with self.assertRaises(PermissionDenied):
            execute(actor=SimpleNamespace(
                is_active=True, role=Role.TECHNICIAN
            ))

    def test_no_token_rejected(self):
        with self.assertRaises(PermissionDenied):
            execute(bearer_token="")

    def test_wrong_envelope_response_rejected(self):
        def wrong(path, token, *, pdf=False):
            if path.endswith("/recipients") or path.endswith("/tabs"):
                return {}
            if pdf:
                return PDF + b"A"
            return {"envelopeId": ACCOUNT, "status": "completed"}
        with self.assertRaises(ValidationError):
            execute(reader=wrong)

    def test_noncompleted_status_rejected(self):
        def incomplete(path, token, *, pdf=False):
            result = reader(path, token, pdf=pdf)
            if path.endswith(ENVELOPE):
                return {"envelopeId": ENVELOPE, "status": "sent"}
            return result
        with self.assertRaises(ValidationError):
            execute(reader=incomplete)

    def test_identical_pdfs_rejected(self):
        def same_pdf(path, token, *, pdf=False):
            return PDF if pdf else reader(path, token)
        with self.assertRaises(ValidationError):
            execute(reader=same_pdf)

    def test_retrieval_gate_disabled_by_default(self):
        with (
            patch(M + ".settings") as settings,
            patch(M + ".os.environ", {}),
        ):
            settings.ENVIRONMENT = "development"
            settings.DEBUG = True
            with self.assertRaises(PermissionDenied):
                retrieve_inspection_sandbox_evidence(
                    actor=None, account_id=ACCOUNT,
                    envelope_id=ENVELOPE, bearer_token="", reader=reader
                )

    def test_no_live_provider_network_request(self):
        with patch(M + "._reader", side_effect=AssertionError(
            "Unexpected network request"
        )) as network:
            result = execute()
            self.assertFalse(result.provider_signature_verified)
            network.assert_not_called()


class ProviderAuditEvent5146Tests(TestCase):
    def test_history_collected_without_signature_trust(self):
        result = execute()
        self.assertEqual(len(result.audit_events["auditEvents"]), 1)
        self.assertFalse(result.provider_signature_verified)
        self.assertFalse(result.signer_identity_verified)
        self.assertFalse(result.completion_authorized)

    def test_missing_audit_history_rejected(self):
        def missing(path, token, *, pdf=False):
            if path.endswith("/audit_events"):
                return {}
            return reader(path, token, pdf=pdf)

        with self.assertRaises(ValidationError):
            execute(reader=missing)

    def test_empty_audit_history_rejected(self):
        def empty(path, token, *, pdf=False):
            if path.endswith("/audit_events"):
                return {"auditEvents": []}
            return reader(path, token, pdf=pdf)

        with self.assertRaises(ValidationError):
            execute(reader=empty)

    def test_malformed_audit_history_rejected(self):
        def malformed(path, token, *, pdf=False):
            if path.endswith("/audit_events"):
                return {"auditEvents": [
                    {"eventFields": "not-a-list"}
                ]}
            return reader(path, token, pdf=pdf)

        with self.assertRaises(ValidationError):
            execute(reader=malformed)
