from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase, override_settings
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import Role
from .expedited_recipient_binding_4567 import assess_unified_recipients

MODULE = "core.expedited_recipient_binding_4567"


@override_settings(ENVIRONMENT="development", DEBUG=True)
class UnifiedRecipientBinding4567Tests(SimpleTestCase):
    def setUp(self):
        self.msr = str(uuid4())
        self.project = str(uuid4())
        self.manager = SimpleNamespace(
            pk=uuid4(), role=Role.INSTALLATION_MANAGER,
            is_active=True, email="manager@example.invalid",
            get_full_name=lambda: "Fictional Manager",
        )
        self.comptroller = SimpleNamespace(
            pk=uuid4(), role=Role.COMPTROLLER,
            is_active=True, email="comptroller@example.invalid",
            get_full_name=lambda: "Fictional Comptroller",
        )
        self.manager_evidence = SimpleNamespace(
            pk=uuid4(), kind="EXPEDITED_MANAGER_DECISION",
            created_by_id=self.manager.pk, digest="a" * 64,
            data={"msr_id": self.msr, "proposed_date": "2026-11-15"},
        )
        self.review_evidence = SimpleNamespace(
            pk=uuid4(), kind="EXPEDITED_SERVICE_REVIEW",
            created_by_id=self.comptroller.pk, digest="b" * 64,
            data={"msr_id": self.msr, "proposed_date": "2026-11-15"},
        )
        self.bound = {
            "project_id": self.project, "msr_id": self.msr,
            "msr_version": 3,
            "snapshot_sha256": "c" * 64,
            "proposed_date": "2026-11-15",
            "administrative_chain_reviewed": True,
            "send_authorized": False, "installation_authorized": False,
            "administrative_records": {
                "manager_decision_id": str(self.manager_evidence.pk),
                "manager_decision_digest": self.manager_evidence.digest,
                "review_id": str(self.review_evidence.pk),
                "review_digest": self.review_evidence.digest,
            },
        }
        self.customer = {
            key: self.bound[key] for key in (
                "project_id", "msr_id", "msr_version",
                "snapshot_sha256", "proposed_date"
            )
        }
        self.customer.update({
            "customer_signer_name": "Fictional Customer",
            "customer_signer_email": "customer@example.invalid",
            "commercial_signer_authorization_id": str(uuid4()),
            "expedited_signer_authorized": False,
            "send_authorized": False, "installation_authorized": False,
        })

    def assess(self):
        def get_evidence(**kwargs):
            found = None
            for row in (self.manager_evidence, self.review_evidence):
                if (
                    str(row.pk) == str(kwargs.get("pk"))
                    and row.kind == kwargs.get("kind")
                    and self.msr == str(kwargs.get("msr_id"))
                ):
                    found = row
            return SimpleNamespace(first=lambda: found)

        def get_user(**kwargs):
            found = next(
                (user for user in (self.manager, self.comptroller)
                 if str(user.pk) == str(kwargs.get("pk"))),
                None,
            )
            return SimpleNamespace(first=lambda: found)

        with (
            patch(f"{MODULE}.assess_unified_signing_preflight",
                  return_value=self.bound),
            patch(f"{MODULE}.assess_expedited_customer_identity",
                  return_value=self.customer),
            patch(f"{MODULE}.ProjectEvidence.objects.filter",
                  side_effect=get_evidence),
            patch(f"{MODULE}.User.objects.filter",
                  side_effect=get_user),
        ):
            return assess_unified_recipients(
                actor=SimpleNamespace(pk=uuid4()),
                project_id=self.project,
            )

    def test_three_ordered_recipients_no_send_authority(self):
        result = self.assess()
        self.assertEqual([x["role"] for x in result["recipients"]], [
            "CUSTOMER", "INSTALLATION_MANAGER", "COMPTROLLER",
        ])
        self.assertEqual([x["routing_order"] for x in result["recipients"]],
                         [1, 2, 3])
        self.assertFalse(result["expedited_signer_authorized"])
        self.assertFalse(result["send_authorized"])
        self.assertFalse(result["installation_authorized"])

    def test_mismatched_customer_msr_rejected(self):
        self.customer["msr_id"] = str(uuid4())
        with self.assertRaises(ValidationError):
            self.assess()

    def test_changed_manager_digest_rejected(self):
        self.manager_evidence.digest = "d" * 64
        with self.assertRaises(ValidationError):
            self.assess()

    def test_wrong_reviewer_role_rejected(self):
        self.comptroller.role = Role.INSTALLATION_MANAGER
        with self.assertRaises(PermissionDenied):
            self.assess()

    def test_inactive_manager_rejected(self):
        self.manager.is_active = False
        with self.assertRaises(PermissionDenied):
            self.assess()

    def test_missing_reviewer_rejected(self):
        self.comptroller_evidence = self.review_evidence
        self.review_evidence.pk = uuid4()
        with self.assertRaises(ValidationError):
            self.assess()

    def test_same_email_rejected(self):
        self.comptroller.email = self.manager.email
        with self.assertRaises(ValidationError):
            self.assess()

    def test_customer_email_same_as_manager_rejected(self):
        self.customer["customer_signer_email"] = self.manager.email
        with self.assertRaises(ValidationError):
            self.assess()

    def test_missing_reviewer_name_rejected(self):
        self.manager.get_full_name = lambda: ""
        with self.assertRaises(ValidationError):
            self.assess()

    def test_preflight_sending_claim_rejected(self):
        self.bound["send_authorized"] = True
        with self.assertRaises(ValidationError):
            self.assess()

    @override_settings(ENVIRONMENT="production", DEBUG=False)
    def test_production_disabled(self):
        with self.assertRaises(PermissionDenied):
            assess_unified_recipients(
                actor=SimpleNamespace(pk=uuid4()),
                project_id=self.project,
            )
