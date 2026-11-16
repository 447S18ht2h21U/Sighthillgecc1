import os
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase, override_settings

from core.installation_provider_oauth_4979 import Role
from core.installation_sandbox_draft_transport_5173 import (
    _gate,
    _validate_draft_payload,
    SandboxDraftCreation5173,
)


def sample_payload():
    return {
        "status": "created",
        "emailSubject": "GECC Inspection Test",
        "documents": [{
            "documentId": "1",
            "fileExtension": "pdf",
            "documentBase64": "UEZERg==",
        }],
        "recipients": {
            "signers": [{
                "recipientId": "1",
                "tabs": {
                    "radioGroupTabs": [{}, {}, {}, {}, {}],
                    "signHereTabs": [{}],
                    "dateSignedTabs": [{}],
                },
            }],
        },
    }


class SandboxDraftSafety5173Tests(SimpleTestCase):
    @override_settings(ENVIRONMENT="development", DEBUG=True)
    def test_draft_disabled_without_explicit_flag(self):
        actor = SimpleNamespace(
            pk=1, is_active=True, role=Role.CEO
        )
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(PermissionDenied):
                _gate(actor)

    @override_settings(ENVIRONMENT="development", DEBUG=True)
    def test_authorized_roles_under_explicit_flag(self):
        with patch.dict(
            os.environ,
            {"GECC_IM_SANDBOX_DRAFT_CREATE_ENABLED": "1"},
        ):
            for role in (Role.CEO, Role.SALES_MANAGER):
                actor = SimpleNamespace(
                    pk=1, is_active=True, role=role
                )
                _gate(actor)

    @override_settings(ENVIRONMENT="development", DEBUG=True)
    def test_unauthorized_role_rejected(self):
        actor = SimpleNamespace(
            pk=1, is_active=True, role=Role.COMPTROLLER
        )
        with patch.dict(
            os.environ,
            {"GECC_IM_SANDBOX_DRAFT_CREATE_ENABLED": "1"},
        ):
            with self.assertRaises(PermissionDenied):
                _gate(actor)

    @override_settings(ENVIRONMENT="production", DEBUG=False)
    def test_production_cannot_enable_draft(self):
        actor = SimpleNamespace(
            pk=1, is_active=True, role=Role.CEO
        )
        with patch.dict(
            os.environ,
            {"GECC_IM_SANDBOX_DRAFT_CREATE_ENABLED": "1"},
        ):
            with self.assertRaises(PermissionDenied):
                _gate(actor)

    def test_only_created_draft_accepted(self):
        payload = sample_payload()
        self.assertIs(_validate_draft_payload(payload), payload)
        payload["status"] = "sent"
        with self.assertRaises(ValidationError):
            _validate_draft_payload(payload)

    def test_required_inspection_tabs_enforced(self):
        payload = sample_payload()
        payload["recipients"]["signers"][0]["tabs"][
            "radioGroupTabs"
        ].pop()
        with self.assertRaises(ValidationError):
            _validate_draft_payload(payload)

    def test_results_never_claim_signing_or_completion(self):
        result = SandboxDraftCreation5173(
            account_id="sandbox", envelope_id="draft", status="created"
        )
        self.assertFalse(result.sent)
        self.assertFalse(result.signature_verified)
        self.assertFalse(result.completion_authorized)