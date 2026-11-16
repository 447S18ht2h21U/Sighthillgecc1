import os
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase, override_settings

from core import installation_draft_oauth_5181 as service
from core.installation_provider_oauth_4979 import Role


FLAG = "GECC_IM_DRAFT_OAUTH_TEST_ENABLED"


@override_settings(ENVIRONMENT="development", DEBUG=True)
class InspectionDraftOAuth5181Tests(SimpleTestCase):

    def reviewer(self, role=Role.COMPTROLLER):
        return SimpleNamespace(pk=8, is_active=True, role=role)

    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(PermissionDenied):
                service._gate(self.reviewer())

    def test_ceo_cannot_act_as_sandbox_reviewer(self):
        with patch.dict(os.environ, {FLAG: "1"}):
            with self.assertRaises(PermissionDenied):
                service._gate(self.reviewer(Role.CEO))

    def test_sales_manager_cannot_act_as_sandbox_reviewer(self):
        with patch.dict(os.environ, {FLAG: "1"}):
            with self.assertRaises(PermissionDenied):
                service._gate(self.reviewer(Role.SALES_MANAGER))

    def test_begin_requires_explicit_confirmation(self):
        with patch.object(
            service, "_gate", return_value=self.reviewer()
        ):
            with self.assertRaises(ValidationError):
                service.begin(
                    actor=self.reviewer(),
                    session_key="session",
                    intent_id="intent",
                    envelope=object(),
                    confirmed=False,
                )

    def test_begin_preserves_no_provider_authority(self):
        intent = SimpleNamespace(
            pk="intent-1",
            digest="a" * 64,
            data={"draft_payload_sha256": "b" * 64},
        )
        project = SimpleNamespace(pk="project-1")

        with (
            patch.object(
                service, "_gate", return_value=self.reviewer()
            ),
            patch.object(
                service, "_authorization",
                return_value=(intent, project)
            ),
            patch.object(
                service.docusign, "begin",
                return_value={"authorization_url": "sandbox-test-url"}
            ) as oauth,
            patch.object(service, "audit") as audit,
        ):
            result = service.begin(
                actor=self.reviewer(),
                session_key="test-session",
                intent_id="intent-1",
                envelope=object(),
                confirmed=True,
            )

            context = oauth.call_args.kwargs["context"]
            self.assertEqual(
                context["operation"], service.OPERATION
            )
            self.assertFalse(context["provider_request_authorized"])
            self.assertFalse(context["send_authorized"])
            self.assertFalse(result["project_completion_authorized"])
            audit.assert_called_once()

    def test_callback_rejects_wrong_operation(self):
        challenge = SimpleNamespace(
            actor_id=8,
            context={
                "operation": "SANDBOX_SIGNING_SEND",
                "provider_request_authorized": False,
                "send_authorized": False,
            },
        )
        with patch.object(
            service, "_gate", return_value=self.reviewer()
        ):
            with self.assertRaises(PermissionDenied):
                service.finish(
                    self.reviewer(), challenge, {}, "test-token"
                )

    def test_callback_rejects_send_authority(self):
        challenge = SimpleNamespace(
            actor_id=8,
            context={
                "operation": service.OPERATION,
                "provider_request_authorized": False,
                "send_authorized": True,
            },
        )
        with patch.object(
            service, "_gate", return_value=self.reviewer()
        ):
            with self.assertRaises(PermissionDenied):
                service.finish(
                    self.reviewer(), challenge, {}, "test-token"
                )

    def test_dispatch_is_explicit_before_generic_draft(self):
        from pathlib import Path

        source = Path("core/docusign.py").read_text(
            encoding="utf-8-sig"
        )

        marker = (
            "challenge.context.get('operation') "
            "== 'SANDBOX_IM_DRAFT_CONTEXT_5181'"
        )

        self.assertIn(marker, source)
        self.assertLess(
            source.index(marker),
            source.index("return finish_draft(actor, challenge, config, token)")
        )