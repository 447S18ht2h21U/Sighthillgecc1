import json
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase, override_settings

from core import docusign
from core import installation_sandbox_draft_transport_5173 as transport
from core.installation_provider_oauth_4979 import Role
from core.test_installation_sandbox_draft_transport_5173 import sample_payload


ACCOUNT = "73fa3720-0d83-4dc5-a081-ab5ba6fb8160"
ENVELOPE = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
FLAG = "GECC_IM_SANDBOX_DRAFT_CREATE_ENABLED"


class FakeOfflineEnvelope:
    def __init__(self, payload=None):
        self.state = "LOCAL_DRAFT_NOT_SUBMITTED"
        self.envelope_id = None
        self.provider_signed = False
        self.completion_authorized = False
        self.request = payload if payload is not None else sample_payload()


@override_settings(ENVIRONMENT="development", DEBUG=True)
class DraftProviderBoundary5174Tests(SimpleTestCase):

    def invoke(self, *, actor_role=Role.CEO, payload=None,
               provider_status="created", account=ACCOUNT,
               flag="1", response_status=201):
        actor = SimpleNamespace(
            pk=1, is_active=True, role=actor_role
        )
        envelope = FakeOfflineEnvelope(payload)

        with (
            patch.dict(os.environ, {FLAG: flag}),
            patch.object(
                transport, "OfflineInstallationEnvelope",
                FakeOfflineEnvelope
            ),
            patch.object(
                docusign, "configuration",
                return_value={"blockers": [], "account_id": ACCOUNT}
            ),
            patch.object(
                transport.http.client, "HTTPSConnection"
            ) as connection,
        ):
            response = Mock()
            response.status = response_status
            response.read.return_value = json.dumps({
                "status": provider_status,
                "envelopeId": ENVELOPE,
            }).encode("utf-8")
            connection.return_value.getresponse.return_value = response

            result = transport.create_sandbox_inspection_draft(
                actor=actor,
                envelope=envelope,
                account_id=account,
                bearer_token="sandbox_test_token_not_real",
            )

            return result, connection

    def test_success_creates_only_draft(self):
        result, connection = self.invoke()
        self.assertEqual(result.envelope_id, ENVELOPE)
        self.assertEqual(result.status, "created")
        self.assertFalse(result.sent)
        self.assertFalse(result.signature_verified)
        self.assertFalse(result.completion_authorized)

        connection.assert_called_once_with(
            "demo.docusign.net", timeout=15
        )

        args, kwargs = connection.return_value.request.call_args
        self.assertEqual(args[0], "POST")
        self.assertEqual(
            args[1],
            f"/restapi/v2.1/accounts/{ACCOUNT}/envelopes"
        )
        self.assertEqual(
            json.loads(kwargs["body"])["status"], "created"
        )
        self.assertEqual(
            kwargs["headers"]["Accept"], "application/json"
        )
        connection.return_value.close.assert_called_once()

    def test_sales_manager_may_create_draft(self):
        result, _ = self.invoke(actor_role=Role.SALES_MANAGER)
        self.assertEqual(result.status, "created")

    def test_comptroller_cannot_create_draft(self):
        with self.assertRaises(PermissionDenied):
            self.invoke(actor_role=Role.COMPTROLLER)

    def test_disabled_flag_prevents_draft(self):
        with self.assertRaises(PermissionDenied):
            self.invoke(flag="0")

    def test_sent_payload_rejected_before_provider(self):
        payload = sample_payload()
        payload["status"] = "sent"
        with self.assertRaises(ValidationError):
            self.invoke(payload=payload)

    def test_provider_sent_status_rejected(self):
        with self.assertRaises(ValidationError):
            self.invoke(provider_status="sent")

    def test_wrong_provider_account_rejected(self):
        wrong = "11111111-2222-4333-8444-555555555555"
        with self.assertRaises(PermissionDenied):
            self.invoke(account=wrong)

    def test_provider_http_error_rejected(self):
        with self.assertRaises(ValidationError):
            self.invoke(response_status=403)

    def test_invalid_provider_envelope_id_rejected(self):
        with (
            patch.dict(os.environ, {FLAG: "1"}),
            patch.object(
                transport, "OfflineInstallationEnvelope",
                FakeOfflineEnvelope
            ),
            patch.object(
                docusign, "configuration",
                return_value={"blockers": [], "account_id": ACCOUNT}
            ),
            patch.object(
                transport.http.client, "HTTPSConnection"
            ) as connection,
        ):
            response = Mock()
            response.status = 201
            response.read.return_value = (
                b'{"status":"created","envelopeId":"not-a-uuid"}'
            )
            connection.return_value.getresponse.return_value = response

            with self.assertRaises(ValidationError):
                transport.create_sandbox_inspection_draft(
                    actor=SimpleNamespace(
                        pk=1, is_active=True, role=Role.CEO
                    ),
                    envelope=FakeOfflineEnvelope(),
                    account_id=ACCOUNT,
                    bearer_token="sandbox_test_token_not_real",
                )

            connection.return_value.close.assert_called_once()