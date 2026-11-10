
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Role
from .expedited_envelope_preview_4568 import build_unified_envelope_preview
from .expedited_offline_envelope_4568 import assemble_offline_candidate
from .expedited_three_signer_evidence_4568 import (
    validate_three_signer_observation,
)


@override_settings(ENVIRONMENT="development", DEBUG=True)
class ThreeSignerEvidence4568Tests(SimpleTestCase):
    def setUp(self):
        self.actor = SimpleNamespace(
            pk=uuid4(), role=Role.SALES_MANAGER, is_active=True
        )
        identity = {
            "project_id": str(uuid4()),
            "msr_id": str(uuid4()),
            "msr_version": 3,
            "snapshot_sha256": "a" * 64,
            "proposed_date": "2026-11-15",
            "envelope_count": 1,
            "documents": ["CUSTOMER_SOW", "EXPEDITED_SERVICE"],
            "recipients": [
                {
                    "role": role, "recipient_id": str(n),
                    "routing_order": n,
                    "name": "Fictional " + role,
                    "email": "fictional%d@example.invalid" % n,
                }
                for n, role in enumerate(
                    ("CUSTOMER", "INSTALLATION_MANAGER", "COMPTROLLER"), 1
                )
            ],
            "expedited_signer_authorized": False,
            "send_authorized": False,
            "installation_authorized": False,
        }
        module = "core.expedited_envelope_preview_4568"
        with (
            patch(f"{module}.User.objects.filter") as users,
            patch(f"{module}.assess_unified_recipients",
                  return_value=identity),
        ):
            users.return_value.first.return_value = self.actor
            preview = build_unified_envelope_preview(
                actor=self.actor, project_id=identity["project_id"]
            )
        self.offline = assemble_offline_candidate(preview=preview)
        self.envelope_id = str(uuid4())
        self.summary = {
            "envelopeId": self.envelope_id,
            "status": "completed",
            "completedDateTime": "2026-11-15T18:00:00Z",
        }
        self.recipients = {"signers": []}
        dates = (
            "2026-11-15T15:00:00Z",
            "2026-11-15T16:00:00Z",
            "2026-11-15T17:00:00Z",
        )

        for index, original in enumerate(
            self.offline["recipients"]["signers"]
        ):
            tabs = deepcopy(original["tabs"])
            for tab in tabs["signHereTabs"]:
                tab["status"] = "signed"
            for tab in tabs["textTabs"]:
                if tab["tabLabel"] == "expedited_customer_reason":
                    tab["value"] = "Customer personally requests earlier service."
            for tab in tabs["initialHereTabs"]:
                if "conditionalParentValue" in tab:
                    tab["value"] = (
                        "FC" if tab["conditionalParentValue"] == "APPROVE"
                        else ""
                    )
                else:
                    tab["value"] = "FC"
            for group in tabs.get("radioGroupTabs", []):
                for radio in group["radios"]:
                    radio["selected"] = (
                        "true" if radio["value"] == "APPROVE" else "false"
                    )

            self.recipients["signers"].append({
                "recipientId": original["recipientId"],
                "routingOrder": original["routingOrder"],
                "name": original["name"],
                "email": original["email"],
                "status": "completed",
                "signedDateTime": dates[index],
                "tabs": tabs,
            })

    def check(self):
        return validate_three_signer_observation(
            expected_envelope_id=self.envelope_id,
            offline_envelope=self.offline,
            summary=self.summary,
            recipients=self.recipients,
        )

    def test_complete_fictional_metadata_remains_untrusted(self):
        result = self.check()
        self.assertEqual(
            result["manager_candidate_decision"], "APPROVED"
        )
        self.assertFalse(result["provider_authenticated"])
        self.assertFalse(result["installation_authorized"])

    def test_missing_third_signer_rejected(self):
        self.recipients["signers"].pop()
        with self.assertRaises(ValidationError):
            self.check()

    def test_swapped_signer_rejected(self):
        self.recipients["signers"].reverse()
        with self.assertRaises(ValidationError):
            self.check()

    def test_noncompleted_envelope_rejected(self):
        self.summary["status"] = "sent"
        with self.assertRaises(ValidationError):
            self.check()

    def test_changed_envelope_identity_rejected(self):
        self.summary["envelopeId"] = str(uuid4())
        with self.assertRaises(ValidationError):
            self.check()

    def test_missing_customer_explanation_rejected(self):
        for tab in self.recipients["signers"][0]["tabs"]["textTabs"]:
            if tab["tabLabel"] == "expedited_customer_reason":
                tab["value"] = ""
        with self.assertRaises(ValidationError):
            self.check()

    def test_two_reviewer_choices_rejected(self):
        radios = self.recipients["signers"][1]["tabs"][
            "radioGroupTabs"
        ][0]["radios"]
        radios[1]["selected"] = "true"
        with self.assertRaises(ValidationError):
            self.check()

    def test_missing_selected_initials_rejected(self):
        tabs = self.recipients["signers"][2]["tabs"]["initialHereTabs"]
        for tab in tabs:
            if tab.get("conditionalParentValue") == "APPROVE":
                tab["value"] = ""
        with self.assertRaises(ValidationError):
            self.check()

    def test_unselected_initials_cannot_count_as_approval(self):
        tabs = self.recipients["signers"][1]["tabs"]["initialHereTabs"]
        for tab in tabs:
            if tab.get("conditionalParentValue") == "REJECT":
                tab["value"] = "FC"
        with self.assertRaises(ValidationError):
            self.check()

    def test_rejection_is_never_installation_authority(self):
        radios = self.recipients["signers"][1]["tabs"][
            "radioGroupTabs"
        ][0]["radios"]
        radios[0]["selected"] = "false"
        radios[1]["selected"] = "true"
        for tab in self.recipients["signers"][1]["tabs"]["initialHereTabs"]:
            if "conditionalParentValue" in tab:
                tab["value"] = (
                    "FC" if tab["conditionalParentValue"] == "REJECT"
                    else ""
                )
        result = self.check()
        self.assertEqual(result["manager_candidate_decision"], "REJECTED")
        self.assertFalse(result["expedited_authorized"])
        self.assertFalse(result["installation_authorized"])

    def test_backdated_or_reversed_signing_order_rejected(self):
        self.recipients["signers"][2]["signedDateTime"] = (
            "2026-11-15T14:00:00Z"
        )
        with self.assertRaises(ValidationError):
            self.check()

    def test_signature_after_envelope_completion_rejected(self):
        self.recipients["signers"][1]["signedDateTime"] = (
            "2026-11-15T19:00:00Z"
        )
        with self.assertRaises(ValidationError):
            self.check()

    @override_settings(ENVIRONMENT="production", DEBUG=False)
    def test_production_rejected(self):
        with self.assertRaises(PermissionDenied):
            self.check()
