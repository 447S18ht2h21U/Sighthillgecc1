"""Focused offline integration: actual rendered PDF through envelope request."""
from dataclasses import replace
import base64
from hashlib import sha256
from unittest import TestCase
from unittest.mock import patch

from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .test_installation_docusign_placement_4960 import (
    actual_form_and_contract,
)
from .installation_docusign_placement_4960 import (
    build_offline_inspection_tab_plan,
)
from .installation_docusign_envelope_4962 import (
    build_offline_installation_envelope,
)

M = "core.installation_docusign_envelope_4962"


def candidate():
    form, contract = actual_form_and_contract()
    plan = build_offline_inspection_tab_plan(
        contract=contract,
        pdf_bytes=form.pdf,
    )
    return form, contract, plan


class OfflineInstallationEnvelope4962Tests(TestCase):
    def test_actual_pdf_roundtrip_preserves_every_byte(self):
        form, contract, plan = candidate()
        package = build_offline_installation_envelope(
            contract=contract, plan=plan, unsigned_pdf=form.pdf
        )
        encoded = package.request["documents"][0]["documentBase64"]
        self.assertEqual(base64.b64decode(encoded), form.pdf)
        self.assertEqual(
            sha256(base64.b64decode(encoded)).hexdigest(),
            package.unsigned_pdf_sha256,
        )

    def test_only_one_intended_manager_signer(self):
        form, contract, plan = candidate()
        package = build_offline_installation_envelope(
            contract=contract, plan=plan, unsigned_pdf=form.pdf
        )
        signer, = package.request["recipients"]["signers"]
        self.assertEqual(signer["email"], contract.signer_email)
        self.assertEqual(signer["name"], contract.signer_name)
        self.assertEqual(signer["recipientId"], "1")
        self.assertEqual(package.request["status"], "created")

    def test_five_required_groups_and_two_signature_tabs(self):
        form, contract, plan = candidate()
        package = build_offline_installation_envelope(
            contract=contract, plan=plan, unsigned_pdf=form.pdf
        )
        tabs = package.request["recipients"]["signers"][0]["tabs"]
        self.assertEqual(len(tabs["radioGroupTabs"]), 5)
        self.assertEqual(len(tabs["signHereTabs"]), 1)
        self.assertEqual(len(tabs["dateSignedTabs"]), 1)
        self.assertTrue(all(
            group["required"] == "true"
            for group in tabs["radioGroupTabs"]
        ))

    def test_customer_survey_is_not_manager_tabs(self):
        form, contract, plan = candidate()
        package = build_offline_installation_envelope(
            contract=contract, plan=plan, unsigned_pdf=form.pdf
        )
        tabs = package.request["recipients"]["signers"][0]["tabs"]
        self.assertTrue(all(
            not group["groupName"].startswith("survey_")
            for group in tabs["radioGroupTabs"]
        ))

    def test_changed_pdf_rejected(self):
        form, contract, plan = candidate()
        with self.assertRaises(ValidationError):
            build_offline_installation_envelope(
                contract=contract,
                plan=plan,
                unsigned_pdf=form.pdf + b"altered",
            )

    def test_forged_provider_trust_rejected(self):
        form, contract, plan = candidate()
        with self.assertRaises(ValidationError):
            build_offline_installation_envelope(
                contract=replace(
                    contract,
                    provider_signature_verified=True,
                ),
                plan=plan,
                unsigned_pdf=form.pdf,
            )

    def test_offline_package_is_deterministic_and_untrusted(self):
        form, contract, plan = candidate()
        first = build_offline_installation_envelope(
            contract=contract, plan=plan, unsigned_pdf=form.pdf
        )
        second = build_offline_installation_envelope(
            contract=contract, plan=plan, unsigned_pdf=form.pdf
        )
        self.assertEqual(
            first.envelope_package_sha256,
            second.envelope_package_sha256,
        )
        self.assertIsNone(first.envelope_id)
        self.assertFalse(first.provider_validated)
        self.assertFalse(first.provider_tabs_installed)
        self.assertFalse(first.provider_signed)
        self.assertFalse(first.inspection_findings_verified)
        self.assertFalse(first.customer_survey_authenticated)
        self.assertFalse(first.completion_authorized)

    @patch(M + ".settings")
    def test_production_assembly_denied(self, settings):
        settings.ENVIRONMENT = "production"
        settings.DEBUG = False
        with self.assertRaises(PermissionDenied):
            build_offline_installation_envelope(
                contract=None, plan=None, unsigned_pdf=None
            )
