
import base64
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import PermissionDenied

from .models import Role
from .expedited_envelope_preview_4568 import build_unified_envelope_preview
from .expedited_offline_envelope_4568 import (
    assemble_offline_candidate, build_offline_for_project,
)

MODULE = "core.expedited_offline_envelope_4568"


@override_settings(ENVIRONMENT="development", DEBUG=True)
class OfflineEnvelope4568Tests(SimpleTestCase):
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
                    "recipient_id": str(number),
                    "routing_order": number,
                    "name": f"Fictional {role}",
                    "email": f"fictional{number}@example.invalid",
                }
                for number, role in enumerate(
                    ("CUSTOMER", "INSTALLATION_MANAGER", "COMPTROLLER"),
                    1,
                )
            ],
            "expedited_signer_authorized": False,
            "send_authorized": False,
            "installation_authorized": False,
        }

    def preview(self):
        path = "core.expedited_envelope_preview_4568"
        with (
            patch(f"{path}.User.objects.filter") as users,
            patch(
                f"{path}.assess_unified_recipients",
                return_value=self.identity,
            ),
        ):
            users.return_value.first.return_value = self.sender
            return build_unified_envelope_preview(
                actor=self.sender,
                project_id=self.identity["project_id"],
            )

    def test_original_pdfs_and_three_signers(self):
        preview = self.preview()
        result = assemble_offline_candidate(preview=preview)
        self.assertEqual(result["status"], "UNSENDABLE_OFFLINE_CANDIDATE")
        self.assertEqual(len(result["documents"]), 2)
        self.assertEqual(len(result["recipients"]["signers"]), 3)
        for doc in result["documents"]:
            raw = base64.b64decode(doc["documentBase64"], validate=True)
            expected = next(
                d["pdf_sha256"] for d in preview["documents"]
                if d["documentId"] == doc["documentId"]
            )
            self.assertEqual(sha256(raw).hexdigest().upper(), expected)
        self.assertFalse(result["send_authorized"])

    def test_two_independent_reviewers(self):
        result = assemble_offline_candidate(preview=self.preview())
        for recipient in result["recipients"]["signers"][1:]:
            tabs = recipient["tabs"]
            self.assertEqual(len(tabs["radioGroupTabs"]), 1)
            self.assertEqual(len(tabs["radioGroupTabs"][0]["radios"]), 2)
            self.assertEqual(len(tabs["initialHereTabs"]), 2)

    def test_provider_signed_dates_not_prefilled(self):
        result = assemble_offline_candidate(preview=self.preview())
        for recipient in result["recipients"]["signers"]:
            for tab in recipient["tabs"]["dateSignedTabs"]:
                self.assertNotIn("value", tab)

    def test_business_date_distinct_from_signing_date(self):
        result = assemble_offline_candidate(preview=self.preview())
        dates = [
            tab for recipient in result["recipients"]["signers"]
            for tab in recipient["tabs"]["textTabs"]
            if tab["tabLabel"] in (
                "sow_proposed_date", "expedited_requested_date"
            )
        ]
        self.assertEqual(len(dates), 2)
        self.assertTrue(all(tab["locked"] == "true" for tab in dates))

    def test_missing_approved_pdf_rejected(self):
        with self.assertRaises(ValidationError):
            assemble_offline_candidate(
                preview=self.preview(),
                reference_root=Path("nonexistent-reference-directory"),
            )

    def test_changed_recipient_order_rejected(self):
        preview = self.preview()
        preview["recipients"][1]["routingOrder"] = "1"
        with self.assertRaises(ValidationError):
            assemble_offline_candidate(preview=preview)

    def test_manual_signing_date_rejected(self):
        preview = self.preview()
        preview["recipients"][0]["tabs"]["dateSignedTabs"][0]["value"] = (
            "2026-11-15"
        )
        with self.assertRaises(ValidationError):
            assemble_offline_candidate(preview=preview)

    def test_claimed_send_authority_rejected(self):
        preview = self.preview()
        preview["send_authorized"] = True
        with self.assertRaises(ValidationError):
            assemble_offline_candidate(preview=preview)

    def test_unauthorized_sender_rejected(self):
        preview = self.preview()
        preview["sender_role"] = Role.SALES_ASSOCIATE
        with self.assertRaises(ValidationError):
            assemble_offline_candidate(preview=preview)

    def test_project_builder_reuses_protected_preview(self):
        preview = self.preview()
        with patch(
            f"{MODULE}.build_unified_envelope_preview",
            return_value=preview,
        ) as builder:
            result = build_offline_for_project(
                actor=self.sender, project_id=self.identity["project_id"],
            )
            builder.assert_called_once()
            self.assertFalse(result["installation_authorized"])

    @override_settings(ENVIRONMENT="production", DEBUG=False)
    def test_production_assembly_disabled(self):
        with self.assertRaises(PermissionDenied):
            assemble_offline_candidate(preview={})
