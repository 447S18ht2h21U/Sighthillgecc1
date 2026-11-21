"""Real-model, isolated authorized handoff acceptance."""
import os
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core.test_post_installation_acceptance_4819 import (
    PostInstallationAcceptance4819 as Fixture,
)
from core.test_installation_draft_end_to_end_5259 import (
    InspectionDraftEndToEnd5259 as Chain,
)
from core import installation_sandbox_handoff_5264 as handoff

ACCOUNT = "73fa3720-0d83-4dc5-a081-ab5ba6fb8160"
TOKEN = "synthetic_not_real_token_5264"


@override_settings(DEBUG=True, ENVIRONMENT="development")
class AuthorizedSandboxHandoff5264(TestCase):
    setUp = Fixture.setUp
    capture = Fixture.capture
    review = Fixture.review
    establish_source = Chain.establish_source
    prepare_and_authorize = Chain.prepare_and_authorize

    def run_handoff(self):
        return handoff.create_authorized_sandbox_draft(
            actor=self.fixture.manager,
            project_id=self.project.pk,
            account_id=ACCOUNT,
            bearer_token=TOKEN,
        )

    def test_authorized_handoff_calls_draft_transport_once(self):
        self.prepare_and_authorize()
        draft = SimpleNamespace(
            status="created",
            sent=False,
            signature_verified=False,
            completion_authorized=False,
        )
        with (
            patch.dict(os.environ, {
                "GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED": "1",
            }),
            patch.object(
                handoff, "create_sandbox_inspection_draft",
                return_value=draft,
            ) as transport,
        ):
            result = self.run_handoff()
            self.assertIs(result, draft)
            transport.assert_called_once()
            self.assertEqual(
                transport.call_args.kwargs["actor"].pk,
                self.fixture.manager.pk,
            )
            self.assertEqual(
                transport.call_args.kwargs["account_id"],
                ACCOUNT,
            )
            self.assertEqual(
                transport.call_args.kwargs["envelope"].request["status"],
                "created",
            )

    def test_no_authorization_never_reaches_transport(self):
        self.establish_source()
        with (
            patch.dict(os.environ, {
                "GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED": "1",
            }),
            patch.object(
                handoff, "create_sandbox_inspection_draft"
            ) as transport,
        ):
            with self.assertRaises(ValidationError):
                self.run_handoff()
            transport.assert_not_called()

    def test_changed_package_never_reaches_transport(self):
        self.prepare_and_authorize()
        with (
            patch.dict(os.environ, {
                "GECC_IM_DRAFT_AUTHORIZATION_TEST_ENABLED": "1",
            }),
            patch.object(
                handoff, "_fingerprint",
                return_value="0" * 64,
            ),
            patch.object(
                handoff, "create_sandbox_inspection_draft"
            ) as transport,
        ):
            with self.assertRaises(ValidationError):
                self.run_handoff()
            transport.assert_not_called()
