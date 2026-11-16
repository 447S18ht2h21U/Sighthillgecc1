from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from core import installation_draft_browser_5185 as service
from core import installation_draft_browser_api_5185 as api


class InstallationDraftBrowser5185Tests(SimpleTestCase):
    def setUp(self):
        self.actor = SimpleNamespace(pk=7)
        self.project_id = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"

    def test_pdf_byte_extraction_rejects_unknown_format(self):
        with self.assertRaises(ValidationError):
            service._pdf_bytes(object())

    def test_pdf_byte_extraction_accepts_exact_bytes(self):
        pdf = b"%PDF-1.4\nexample"
        self.assertIs(service._pdf_bytes(pdf), pdf)
        self.assertIs(
            service._pdf_bytes(SimpleNamespace(pdf_bytes=pdf)),
            pdf,
        )

    def test_authorization_requires_explicit_confirmation(self):
        with patch.object(service, "authorization_gate"):
            with self.assertRaises(ValidationError):
                service.authorize(
                    actor=self.actor,
                    project_id=self.project_id,
                    confirmed=False,
                )

    def test_server_generated_package_is_authorized(self):
        envelope = object()

        with (
            patch.object(service, "authorization_gate"),
            patch.object(service, "assemble", return_value=envelope),
            patch.object(
                service,
                "record_draft_intent",
                return_value={
                    "status": "DRAFT_INTENT_RECORDED",
                    "evidence_id": "evidence-1",
                    "digest": "a" * 64,
                },
            ) as record,
        ):
            result = service.authorize(
                actor=self.actor,
                project_id=self.project_id,
                confirmed=True,
            )

            self.assertIs(
                record.call_args.kwargs["envelope"],
                envelope,
            )
            self.assertTrue(record.call_args.kwargs["confirmed"])
            self.assertFalse(result["provider_request_authorized"])
            self.assertFalse(result["send_authorized"])
            self.assertFalse(result["provider_signature_verified"])
            self.assertFalse(result["project_completion_authorized"])

    def test_assembly_uses_server_generated_documents_only(self):
        contract = SimpleNamespace(
            approved_msr_id="msr-1",
            approved_msr_version=2,
        )
        pdf = b"%PDF-1.4\nexample"
        plan = object()
        envelope = SimpleNamespace(
            project_id=self.project_id,
            approved_msr_id="msr-1",
            approved_msr_version=2,
            provider_signed=False,
            completion_authorized=False,
            envelope_id=None,
        )

        with (
            patch.object(service, "authorization_gate"),
            patch.object(
                service,
                "build_unsigned_installation_docusign_contract",
                return_value=contract,
            ) as build_contract,
            patch.object(
                service,
                "render_unsigned_inspection_form",
                return_value=SimpleNamespace(pdf_bytes=pdf),
            ) as render,
            patch.object(
                service,
                "build_offline_inspection_tab_plan",
                return_value=plan,
            ) as build_tabs,
            patch.object(
                service,
                "build_offline_installation_envelope",
                return_value=envelope,
            ) as build_envelope,
        ):
            result = service.assemble(
                actor=self.actor,
                project_id=self.project_id,
            )

        self.assertIs(result, envelope)
        build_contract.assert_called_once_with(
            actor=self.actor,
            project_id=self.project_id,
        )
        render.assert_called_once_with(
            actor=self.actor,
            project_id=self.project_id,
        )
        build_tabs.assert_called_once_with(
            contract=contract,
            pdf_bytes=pdf,
        )
        build_envelope.assert_called_once_with(
            contract=contract,
            plan=plan,
            unsigned_pdf=pdf,
        )

    def test_assembly_rejects_project_mismatch(self):
        envelope = SimpleNamespace(
            project_id="different-project",
            approved_msr_id="msr-1",
            approved_msr_version=2,
            provider_signed=False,
            completion_authorized=False,
            envelope_id=None,
        )

        with (
            patch.object(service, "authorization_gate"),
            patch.object(
                service,
                "build_unsigned_installation_docusign_contract",
                return_value=SimpleNamespace(
                    approved_msr_id="msr-1",
                    approved_msr_version=2,
                ),
            ),
            patch.object(
                service,
                "render_unsigned_inspection_form",
                return_value=b"pdf",
            ),
            patch.object(
                service,
                "build_offline_inspection_tab_plan",
                return_value=object(),
            ),
            patch.object(
                service,
                "build_offline_installation_envelope",
                return_value=envelope,
            ),
        ):
            with self.assertRaises(ValidationError):
                service.assemble(
                    actor=self.actor,
                    project_id=self.project_id,
                )

    def test_api_rejects_extra_fields(self):
        factory = APIRequestFactory()
        request = factory.post(
            "/api/inspection-draft-intents/test/authorize/",
            {
                "confirm_inspection_draft_intent": True,
                "send_envelope": True,
            },
            format="json",
        )

        user = SimpleNamespace(
            is_authenticated=True,
            is_active=True,
            pk=7,
        )
        force_authenticate(request, user=user)

        with patch.object(api, "authorize_intent") as authorization:
            response = api.authorize(request, self.project_id)

        self.assertEqual(response.status_code, 400)
        authorization.assert_not_called()

    def test_api_rejects_false_confirmation(self):
        factory = APIRequestFactory()
        request = factory.post(
            "/api/inspection-draft-intents/test/authorize/",
            {"confirm_inspection_draft_intent": False},
            format="json",
        )

        user = SimpleNamespace(
            is_authenticated=True,
            is_active=True,
            pk=7,
        )
        force_authenticate(request, user=user)

        with patch.object(api, "authorize_intent") as authorization:
            response = api.authorize(request, self.project_id)

        self.assertEqual(response.status_code, 400)
        authorization.assert_not_called()