"""Actual authorized inspection package to simulated DocuSign draft.

All records live in disposable SQLite. HTTPS is intercepted and no
real provider call, persistent database write, or send is permitted.
"""
import json
import os
from unittest.mock import Mock, patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings

from core.test_post_installation_acceptance_4819 import (
    PostInstallationAcceptance4819 as Fixture,
)
from core.test_installation_draft_end_to_end_5259 import (
    InspectionDraftEndToEnd5259 as ExistingChain,
)
from core.installation_draft_browser_5185 import assemble
from core.installation_draft_handoff_5258 import verify_handoff
from core.installation_draft_authorization_5179 import _fingerprint
from core.installation_sandbox_draft_transport_5173 import (
    create_sandbox_inspection_draft,
)
from core import installation_sandbox_draft_transport_5173 as transport
from core import docusign

ACCOUNT = "73fa3720-0d83-4dc5-a081-ab5ba6fb8160"
ENVELOPE = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"
AUTHORIZED_FLAG = "GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED"
TRANSPORT_FLAG = "GECC_IM_SANDBOX_DRAFT_CREATE_ENABLED"


@override_settings(DEBUG=True, ENVIRONMENT="development")
class InspectionSandboxHandoff5263(TestCase):
    setUp = Fixture.setUp
    capture = Fixture.capture
    review = Fixture.review
    establish_source = ExistingChain.establish_source
    prepare_and_authorize = ExistingChain.prepare_and_authorize
    handoff = ExistingChain.handoff

    def test_real_package_matches_authorization_and_stays_draft(self):
        self.prepare_and_authorize()

        with (
            patch.dict(os.environ, {
                AUTHORIZED_FLAG: "1",
                TRANSPORT_FLAG: "1",
            }),
            patch.object(
                docusign, "configuration",
                return_value={
                    "blockers": [],
                    "account_id": ACCOUNT,
                },
            ),
            patch.object(
                transport.http.client, "HTTPSConnection"
            ) as connection,
        ):
            authorized = verify_handoff(
                actor=self.fixture.manager,
                project_id=self.project.pk,
            )
            envelope = assemble(
                actor=self.fixture.manager,
                project_id=self.project.pk,
            )

            self.assertEqual(
                _fingerprint(envelope),
                authorized["draft_payload_sha256"],
            )
            self.assertEqual(
                authorized["state"],
                "OFFLINE_DRAFT_HANDOFF_MATCHED",
            )

            response = Mock()
            response.status = 201
            response.read.return_value = json.dumps({
                "status": "created",
                "envelopeId": ENVELOPE,
            }).encode("utf-8")
            connection.return_value.getresponse.return_value = response

            result = create_sandbox_inspection_draft(
                actor=self.fixture.manager,
                envelope=envelope,
                account_id=ACCOUNT,
                bearer_token="synthetic_token_not_real_5263",
            )

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
                f"/restapi/v2.1/accounts/{ACCOUNT}/envelopes",
            )
            payload = json.loads(kwargs["body"])
            self.assertEqual(payload["status"], "created")
            self.assertEqual(len(payload["documents"]), 1)
            self.assertEqual(
                len(payload["recipients"]["signers"]), 1
            )
            tabs = payload["recipients"]["signers"][0]["tabs"]
            self.assertEqual(len(tabs["radioGroupTabs"]), 5)
            self.assertEqual(len(tabs["signHereTabs"]), 1)
            self.assertEqual(len(tabs["dateSignedTabs"]), 1)
            connection.return_value.close.assert_called_once()

    def test_transport_disabled_without_explicit_flag(self):
        self.prepare_and_authorize()

        with (
            patch.dict(os.environ, {
                AUTHORIZED_FLAG: "1",
                TRANSPORT_FLAG: "0",
            }),
            patch.object(
                transport.http.client, "HTTPSConnection"
            ) as connection,
        ):
            envelope = assemble(
                actor=self.fixture.manager,
                project_id=self.project.pk,
            )
            with self.assertRaises(PermissionDenied):
                create_sandbox_inspection_draft(
                    actor=self.fixture.manager,
                    envelope=envelope,
                    account_id=ACCOUNT,
                    bearer_token="synthetic_token_not_real_5263",
                )
            connection.assert_not_called()

    def test_provider_sent_response_is_rejected(self):
        self.prepare_and_authorize()

        with (
            patch.dict(os.environ, {
                AUTHORIZED_FLAG: "1",
                TRANSPORT_FLAG: "1",
            }),
            patch.object(
                docusign, "configuration",
                return_value={
                    "blockers": [],
                    "account_id": ACCOUNT,
                },
            ),
            patch.object(
                transport.http.client, "HTTPSConnection"
            ) as connection,
        ):
            envelope = assemble(
                actor=self.fixture.manager,
                project_id=self.project.pk,
            )
            response = Mock()
            response.status = 201
            response.read.return_value = json.dumps({
                "status": "sent",
                "envelopeId": ENVELOPE,
            }).encode("utf-8")
            connection.return_value.getresponse.return_value = response

            with self.assertRaises(ValidationError):
                create_sandbox_inspection_draft(
                    actor=self.fixture.manager,
                    envelope=envelope,
                    account_id=ACCOUNT,
                    bearer_token="synthetic_token_not_real_5263",
                )
            connection.return_value.close.assert_called_once()

    def test_missing_authorization_prevents_handoff(self):
        self.establish_source()
        with (
            patch.dict(os.environ, {
                AUTHORIZED_FLAG: "1",
                TRANSPORT_FLAG: "1",
            }),
            patch.object(
                transport.http.client, "HTTPSConnection"
            ) as connection,
        ):
            with self.assertRaises(ValidationError):
                verify_handoff(
                    actor=self.fixture.manager,
                    project_id=self.project.pk,
                )
            connection.assert_not_called()
