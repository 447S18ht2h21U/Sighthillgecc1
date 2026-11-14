from dataclasses import replace
from unittest import TestCase
from unittest.mock import patch
from django.core.exceptions import ValidationError
from rest_framework.exceptions import PermissionDenied

from .test_installation_docusign_placement_4960 import actual_form_and_contract
from .installation_docusign_placement_4960 import build_offline_inspection_tab_plan
from .installation_docusign_tabs_4961 import build_offline_recipient_tabs

M = "core.installation_docusign_tabs_4961"


def candidate():
    form, contract = actual_form_and_contract()
    plan = build_offline_inspection_tab_plan(
        contract=contract, pdf_bytes=form.pdf
    )
    return contract, plan


class OfflineDocuSignTabs4961Tests(TestCase):
    def test_exact_five_radio_groups(self):
        contract, plan = candidate()
        tabs = build_offline_recipient_tabs(contract=contract, plan=plan).tabs
        groups = tabs["radioGroupTabs"]
        self.assertEqual(len(groups), 5)
        self.assertEqual(
            [group["groupName"] for group in groups],
            [f"inspection_{i}" for i in range(1, 6)],
        )
        for group in groups:
            self.assertEqual(group["required"], "true")
            self.assertEqual(
                [radio["value"] for radio in group["radios"]],
                ["YES", "NO"],
            )
            self.assertTrue(all(
                radio["selected"] == "false"
                for radio in group["radios"]
            ))

    def test_real_pdf_coordinates_retained(self):
        contract, plan = candidate()
        tabs = build_offline_recipient_tabs(contract=contract, plan=plan).tabs
        for index, group in enumerate(tabs["radioGroupTabs"]):
            positions = plan.radio_positions[index * 2:index * 2 + 2]
            for radio, original in zip(group["radios"], positions):
                self.assertEqual(radio["xPosition"], str(original.x))
                self.assertEqual(radio["yPosition"], str(original.y))

    def test_signature_and_date_tabs_required(self):
        contract, plan = candidate()
        tabs = build_offline_recipient_tabs(contract=contract, plan=plan).tabs
        self.assertEqual(len(tabs["signHereTabs"]), 1)
        self.assertEqual(len(tabs["dateSignedTabs"]), 1)
        self.assertEqual(
            tabs["signHereTabs"][0]["anchorString"],
            plan.signature_anchor,
        )
        self.assertEqual(
            tabs["dateSignedTabs"][0]["anchorString"],
            plan.date_signed_anchor,
        )

    def test_no_customer_survey_tabs(self):
        contract, plan = candidate()
        tabs = build_offline_recipient_tabs(contract=contract, plan=plan).tabs
        self.assertFalse(any(
            "survey_" in str(item)
            for group in tabs["radioGroupTabs"]
            for item in (group["groupName"],)
        ))

    def test_forged_provider_authorization_rejected(self):
        contract, plan = candidate()
        with self.assertRaises(ValidationError):
            build_offline_recipient_tabs(
                contract=replace(contract, provider_tabs_installed=True),
                plan=plan,
            )
        with self.assertRaises(ValidationError):
            build_offline_recipient_tabs(
                contract=contract,
                plan=replace(plan, provider_authenticated=True),
            )

    def test_mismatched_contract_rejected(self):
        contract, plan = candidate()
        with self.assertRaises(ValidationError):
            build_offline_recipient_tabs(
                contract=replace(contract, contract_sha256="0" * 64),
                plan=plan,
            )

    def test_payload_fingerprint_deterministic_and_untrusted(self):
        contract, plan = candidate()
        first = build_offline_recipient_tabs(contract=contract, plan=plan)
        second = build_offline_recipient_tabs(contract=contract, plan=plan)
        self.assertEqual(first.payload_sha256, second.payload_sha256)
        self.assertFalse(first.provider_validated)
        self.assertFalse(first.tabs_installed)
        self.assertFalse(first.envelope_created)
        self.assertFalse(first.signer_authenticated)
        self.assertFalse(first.findings_verified)
        self.assertFalse(first.completion_authorized)

    @patch(M + ".settings")
    def test_production_denied(self, settings):
        settings.ENVIRONMENT = "production"
        settings.DEBUG = False
        with self.assertRaises(PermissionDenied):
            build_offline_recipient_tabs(contract=None, plan=None)
