
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from .models import Role
from .expedited_envelope_preview_4568 import build_unified_envelope_preview
from .expedited_offline_envelope_4568 import assemble_offline_candidate
from .expedited_tab_contract_4568 import validate_offline_tab_contract


@override_settings(ENVIRONMENT="development", DEBUG=True)
class OfflineTabContract4568Tests(SimpleTestCase):
    def setUp(self):
        self.actor = SimpleNamespace(
            pk=uuid4(), role=Role.SALES_MANAGER, is_active=True
        )
        self.identity = {
            "project_id": str(uuid4()),
            "msr_id": str(uuid4()),
            "msr_version": 3,
            "snapshot_sha256": "a" * 64,
            "proposed_date": "2026-11-15",
            "envelope_count": 1,
            "documents": ["CUSTOMER_SOW", "EXPEDITED_SERVICE"],
            "recipients": [
                {
                    "role": role,
                    "recipient_id": str(index),
                    "routing_order": index,
                    "name": "Fictional " + role,
                    "email": "fictional%d@example.invalid" % index,
                }
                for index, role in enumerate(
                    ("CUSTOMER", "INSTALLATION_MANAGER", "COMPTROLLER"),
                    1,
                )
            ],
            "expedited_signer_authorized": False,
            "send_authorized": False,
            "installation_authorized": False,
        }
        path = "core.expedited_envelope_preview_4568"
        with (
            patch(f"{path}.User.objects.filter") as users,
            patch(f"{path}.assess_unified_recipients",
                  return_value=self.identity),
        ):
            users.return_value.first.return_value = self.actor
            preview = build_unified_envelope_preview(
                actor=self.actor, project_id=self.identity["project_id"]
            )
        self.envelope = assemble_offline_candidate(preview=preview)

    def validate(self):
        return validate_offline_tab_contract(self.envelope)

    def test_complete_offline_contract(self):
        result = self.validate()
        self.assertEqual(result["reviewer_decision_groups"], 2)
        self.assertFalse(result["send_authorized"])

    def test_manager_conditional_parent_tamper_rejected(self):
        tabs = self.envelope["recipients"]["signers"][1]["tabs"]
        tabs["initialHereTabs"][0]["conditionalParentLabel"] = "wrong"
        with self.assertRaises(ValidationError):
            self.validate()

    def test_comptroller_choice_tamper_rejected(self):
        group = self.envelope["recipients"]["signers"][2]["tabs"][
            "radioGroupTabs"
        ][0]
        group["radios"][1]["value"] = "APPROVE"
        with self.assertRaises(ValidationError):
            self.validate()

    def test_preselected_approval_rejected(self):
        group = self.envelope["recipients"]["signers"][1]["tabs"][
            "radioGroupTabs"
        ][0]
        group["radios"][0]["selected"] = "true"
        with self.assertRaises(ValidationError):
            self.validate()

    def test_missing_customer_signature_rejected(self):
        tabs = self.envelope["recipients"]["signers"][0]["tabs"]
        tabs["signHereTabs"].pop()
        with self.assertRaises(ValidationError):
            self.validate()

    def test_manual_manager_signed_date_rejected(self):
        tabs = self.envelope["recipients"]["signers"][1]["tabs"]
        tabs["dateSignedTabs"][0]["value"] = "2026-11-15"
        with self.assertRaises(ValidationError):
            self.validate()

    def test_wrong_recipient_order_rejected(self):
        self.envelope["recipients"]["signers"][2]["routingOrder"] = "1"
        with self.assertRaises(ValidationError):
            self.validate()

    def test_send_claim_rejected(self):
        self.envelope["send_authorized"] = True
        with self.assertRaises(ValidationError):
            self.validate()
