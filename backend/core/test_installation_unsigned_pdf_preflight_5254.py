"""Offline inspection PDF preflight safety tests, no database writes."""
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase, override_settings
from core.models import Role
from core import installation_unsigned_pdf_preflight_5254 as preflight

PROJECT = "project-5254"


@override_settings(ENVIRONMENT="development", DEBUG=True)
class UnsignedPdfPreflight5254Tests(SimpleTestCase):
    def setUp(self):
        self.actor = SimpleNamespace(role=Role.SALES_MANAGER)
        self.status = {
            "project_id": PROJECT,
            "preparation_ready": True,
            "source_stage": "PREPARATION_VERIFIED",
            "authorization_state": "NOT_AUTHORIZED",
            "provider_draft_created": False,
            "provider_request_authorized": False,
            "send_authorized": False,
            "provider_signature_verified": False,
            "project_completion_authorized": False,
        }
        fields = [
            SimpleNamespace(
                field_id=f"inspection_{n}", required=True,
                signer_role="INSTALLATION_MANAGER"
            ) for n in range(1, 6)
        ]
        fields += [
            SimpleNamespace(
                field_id="installation_manager_signature",
                required=True, signer_role="INSTALLATION_MANAGER"
            ),
            SimpleNamespace(
                field_id="installation_manager_signed_date",
                required=True, signer_role="INSTALLATION_MANAGER"
            ),
        ]
        self.contract = SimpleNamespace(
            project_id=PROJECT,
            approved_msr_id="msr",
            approved_msr_version="1",
            source_evidence_id="source",
            preparation_evidence_id="preparation",
            unsigned_pdf_sha256="a" * 64,
            fields=tuple(fields),
            envelope_id=None,
            provider_signature_verified=False,
            inspection_findings_verified=False,
            trusted_installation_evidence=False,
            receipt_issuance_authorized=False,
            project_completion_authorized=False,
        )

    def run_check(self):
        with (
            patch.object(preflight, "inspect_status", return_value=self.status),
            patch.object(
                preflight,
                "build_unsigned_installation_docusign_contract",
                return_value=self.contract,
            ) as builder,
        ):
            result = preflight.verify_unsigned_pdf(
                actor=self.actor, project_id=PROJECT
            )
        return result, builder

    def test_valid_offline_preview_remains_non_authorizing(self):
        result, builder = self.run_check()
        builder.assert_called_once()
        self.assertEqual(result["status"], "UNSIGNED_PDF_VERIFIED_OFFLINE")
        self.assertEqual(result["required_inspection_findings"], 5)
        self.assertEqual(result["required_signature_fields"], 2)
        for field in (
            "document_saved", "provider_envelope_created",
            "document_sent", "provider_signature_verified",
            "receipt_issuance_authorized",
            "project_completion_authorized",
        ):
            self.assertIs(result[field], False)

    def test_comptroller_cannot_prepare_pdf(self):
        self.actor.role = Role.COMPTROLLER
        with self.assertRaises(PermissionDenied):
            self.run_check()

    def test_missing_preparation_fails_before_pdf_build(self):
        self.status["preparation_ready"] = False
        with patch.object(
            preflight,
            "build_unsigned_installation_docusign_contract"
        ) as builder:
            with patch.object(
                preflight, "inspect_status", return_value=self.status
            ):
                with self.assertRaises(ValidationError):
                    preflight.verify_unsigned_pdf(
                        actor=self.actor, project_id=PROJECT
                    )
            builder.assert_not_called()

    def test_unexpected_send_authority_fails_closed(self):
        self.status["send_authorized"] = True
        with patch.object(
            preflight, "inspect_status", return_value=self.status
        ):
            with self.assertRaises(ValidationError):
                preflight.verify_unsigned_pdf(
                    actor=self.actor, project_id=PROJECT
                )

    def test_wrong_project_pdf_is_rejected(self):
        self.contract.project_id = "other-project"
        with self.assertRaises(ValidationError):
            self.run_check()

    def test_missing_signature_field_is_rejected(self):
        self.contract.fields = self.contract.fields[:-1]
        with self.assertRaises(ValidationError):
            self.run_check()
