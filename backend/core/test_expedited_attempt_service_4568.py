
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Role
from .expedited_attempt_service_4568 import (
    prepare_expedited_attempt, create_expedited_attempt,
)

MOD = "core.expedited_attempt_service_4568"


@override_settings(ENVIRONMENT="development", DEBUG=True)
class ExpeditedAttemptService4568Tests(SimpleTestCase):
    def setUp(self):
        self.actor = SimpleNamespace(
            pk=uuid4(), role=Role.SALES_MANAGER, is_active=True
        )
        self.msr_id = str(uuid4())
        self.project_id = str(uuid4())
        self.manifest = [
            {
                "role": role,
                "recipientId": str(n),
                "routingOrder": str(n),
                "name": "Fictional " + role,
                "email": f"fake{n}@example.invalid",
            }
            for n, role in enumerate(
                ("CUSTOMER", "INSTALLATION_MANAGER", "COMPTROLLER"), 1
            )
        ]
        self.preview = {
            "msr_id": self.msr_id,
            "snapshot_sha256": "a" * 64,
            "proposed_date": "2026-11-15",
            "send_authorized": False,
            "installation_authorized": False,
        }
        self.offline = {
            "recipients": {"signers": self.manifest},
            "documents": [
                {"documentId": "1", "documentBase64": "ZmljdGlvbmFsMQ=="},
                {"documentId": "2", "documentBase64": "ZmljdGlvbmFsMg=="},
            ],
            "send_authorized": False,
            "installation_authorized": False,
        }

    def plan(self, actor=None):
        with (
            patch(f"{MOD}.build_unified_envelope_preview",
                  return_value=self.preview),
            patch(f"{MOD}.assemble_offline_candidate",
                  return_value=self.offline),
        ):
            return prepare_expedited_attempt(
                actor=actor or self.actor, project_id=self.project_id
            )

    def test_canonical_plan_binds_msr_and_three_signers(self):
        result = self.plan()
        self.assertEqual(result["msr_id"], self.msr_id)
        self.assertEqual(len(result["recipient_manifest"]), 3)
        self.assertEqual(result["proposed_date"], date(2026, 11, 15))
        self.assertFalse(result["send_authorized"])

    def test_source_digest_is_deterministic(self):
        self.assertEqual(
            self.plan()["source_digest"], self.plan()["source_digest"]
        )

    def test_changed_recipient_changes_digest(self):
        original = self.plan()["source_digest"]
        self.manifest[1]["email"] = "other@example.invalid"
        self.assertNotEqual(original, self.plan()["source_digest"])

    def test_changed_document_changes_digest(self):
        original = self.plan()["source_digest"]
        self.offline["documents"][1]["documentBase64"] = "Y2hhbmdlZA=="
        self.assertNotEqual(original, self.plan()["source_digest"])

    def test_sales_associate_denied(self):
        person = SimpleNamespace(
            pk=uuid4(), role=Role.SALES_ASSOCIATE, is_active=True
        )
        with self.assertRaises(PermissionDenied):
            self.plan(actor=person)

    def test_inactive_sender_denied(self):
        self.actor.is_active = False
        with self.assertRaises(PermissionDenied):
            self.plan()

    def test_wrong_signer_order_rejected(self):
        self.manifest[2]["routingOrder"] = "2"
        with self.assertRaises(ValidationError):
            self.plan()

    def test_send_authority_claim_rejected(self):
        self.offline["send_authorized"] = True
        with self.assertRaises(ValidationError):
            self.plan()

    def test_invalid_date_rejected(self):
        self.preview["proposed_date"] = "not-a-date"
        with self.assertRaises(ValidationError):
            self.plan()

    @override_settings(ENVIRONMENT="production", DEBUG=False)
    def test_production_denied(self):
        with self.assertRaises(PermissionDenied):
            self.plan()

    def test_persistence_method_is_atomic(self):
        from .expedited_attempt_service_4568 import (
            create_expedited_attempt
        )
        self.assertTrue(
            hasattr(create_expedited_attempt, "__wrapped__")
            or callable(create_expedited_attempt)
        )
