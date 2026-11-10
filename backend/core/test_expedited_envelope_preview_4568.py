from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Role
from .expedited_envelope_preview_4568 import (
    build_unified_envelope_preview,
)

MODULE = "core.expedited_envelope_preview_4568"


@override_settings(ENVIRONMENT="development", DEBUG=True)
class UnifiedEnvelopePreview4568Tests(SimpleTestCase):
    def setUp(self):
        self.sender = SimpleNamespace(
            pk=uuid4(), role=Role.SALES_MANAGER, is_active=True,
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
                    "recipient_id": str(n),
                    "routing_order": n,
                    "name": f"Fictional {role}",
                    "email": f"person{n}@example.invalid",
                }
                for n, role in enumerate((
                    "CUSTOMER", "INSTALLATION_MANAGER", "COMPTROLLER"
                ), start=1)
            ],
            "expedited_signer_authorized": False,
            "send_authorized": False,
            "installation_authorized": False,
        }

    def build(self):
        with (
            patch(f"{MODULE}.User.objects.filter") as users,
            patch(f"{MODULE}.assess_unified_recipients",
                  return_value=self.identity),
        ):
            users.return_value.first.return_value = self.sender
            return build_unified_envelope_preview(
                actor=self.sender,
                project_id=self.identity["project_id"],
            )

    def test_sales_manager_can_prepare_unsendable_preview(self):
        result = self.build()
        self.assertEqual(result["sender_role"], Role.SALES_MANAGER)
        self.assertEqual(len(result["documents"]), 2)
        self.assertEqual(len(result["recipients"]), 3)
        self.assertEqual(len(result["reviewer_fields_pending"]), 6)
        self.assertFalse(result["send_authorized"])
        self.assertFalse(result["installation_authorized"])
        self.assertNotIn("documentBase64", str(result))

    def test_ceo_can_prepare_preview(self):
        self.sender.role = Role.CEO
        self.assertEqual(self.build()["sender_role"], Role.CEO)

    def test_sales_associate_is_not_sender(self):
        self.sender.role = Role.SALES_ASSOCIATE
        with self.assertRaises(PermissionDenied):
            self.build()

    def test_installation_manager_is_not_sender(self):
        self.sender.role = Role.INSTALLATION_MANAGER
        with self.assertRaises(PermissionDenied):
            self.build()

    def test_comptroller_is_not_sender(self):
        self.sender.role = Role.COMPTROLLER
        with self.assertRaises(PermissionDenied):
            self.build()

    def test_inactive_sender_is_blocked(self):
        self.sender.is_active = False
        with self.assertRaises(PermissionDenied):
            self.build()

    def test_date_signed_tabs_have_no_manual_value(self):
        result = self.build()
        signed = [
            tab
            for recipient in result["recipients"]
            for tab in recipient["tabs"]["dateSignedTabs"]
        ]
        self.assertEqual(len(signed), 3)
        self.assertTrue(all("value" not in tab for tab in signed))
        self.assertEqual(
            result["signature_dates_source"], "DOCUSIGN_PROVIDER_ONLY"
        )

    def test_original_business_dates_are_locked(self):
        result = self.build()
        populated = [
            tab
            for recipient in result["recipients"]
            for tab in recipient["tabs"]["textTabs"]
            if tab["tabLabel"] in (
                "sow_proposed_date", "expedited_requested_date"
            )
        ]
        self.assertEqual(len(populated), 2)
        self.assertEqual(
            [tab["value"] for tab in populated],
            ["2026-11-15", "2026-11-15"],
        )
        self.assertTrue(all(tab["locked"] == "true" for tab in populated))

    def test_route_change_is_blocked(self):
        self.identity["recipients"][1]["routing_order"] = 1
        with self.assertRaises(ValidationError):
            self.build()

    def test_send_authority_claim_is_blocked(self):
        self.identity["send_authorized"] = True
        with self.assertRaises(ValidationError):
            self.build()

    def test_expedited_authority_claim_is_blocked(self):
        self.identity["expedited_signer_authorized"] = True
        with self.assertRaises(ValidationError):
            self.build()

    @override_settings(ENVIRONMENT="production", DEBUG=False)
    def test_production_is_blocked(self):
        with self.assertRaises(PermissionDenied):
            build_unified_envelope_preview(
                actor=self.sender, project_id=self.identity["project_id"],
            )
