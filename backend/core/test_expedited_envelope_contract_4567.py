from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.test import SimpleTestCase

from .expedited_envelope_contract_4567 import (
    DISTRIBUTION, FIELDS, SIGNING_ORDER, unified_candidate_contract,
)

ROOT = (
    Path(settings.BASE_DIR).parent
    / "docs/reference/GECC-20261107-final-seven"
)


class UnifiedExpeditedEnvelope4567Tests(SimpleTestCase):
    def setUp(self):
        self.data = {
            "reference_root": ROOT,
            "msr_id": str(uuid4()),
            "msr_version": 3,
            "snapshot_sha256": "a" * 64,
            "proposed_date": "2026-11-15",
            "identities": {
                "CUSTOMER": {
                    "name": "Fictional Customer",
                    "email": "customer@example.invalid",
                },
                "INSTALLATION_MANAGER": {
                    "name": "Fictional Manager",
                    "email": "manager@example.invalid",
                },
                "COMPTROLLER": {
                    "name": "Fictional Comptroller",
                    "email": "comptroller@example.invalid",
                },
            },
        }

    def build(self):
        return unified_candidate_contract(**self.data)

    def test_one_envelope_contains_both_approved_documents(self):
        result = self.build()
        self.assertEqual(result["envelope_count"], 1)
        self.assertEqual(
            [(d["document_id"], d["kind"]) for d in result["documents"]],
            [("1", "CUSTOMER_SOW"), ("2", "EXPEDITED_SERVICE")],
        )

    def test_date_is_identical_and_locked_in_both_documents(self):
        fields = {f["key"]: f for f in self.build()["required_fields"]}
        for name in ("sow_proposed_date", "expedited_requested_date"):
            self.assertEqual(fields[name]["value"], "2026-11-15")
            self.assertTrue(fields[name]["locked_to_approved_date"])

    def test_customer_reason_is_personal_and_not_prepopulated(self):
        field = next(
            f for f in self.build()["required_fields"]
            if f["key"] == "expedited_customer_reason"
        )
        self.assertEqual(field["owner"], "CUSTOMER")
        self.assertEqual(field["type"], "MULTILINE_TEXT")
        self.assertTrue(field["must_be_entered_by_customer"])
        self.assertFalse(field["prepopulated"])

    def test_all_signatures_reviews_and_dates_are_required(self):
        result = self.build()
        self.assertEqual(len(result["required_fields"]), len(FIELDS))
        self.assertTrue(all(f["required"] for f in result["required_fields"]))
        self.assertEqual(result["signing_order"], list(SIGNING_ORDER))
        self.assertTrue(result["independent_reviews_required"])

    def test_distribution_roles_and_delivery_evidence(self):
        result = self.build()
        self.assertEqual(result["distribution_roles"], list(DISTRIBUTION))
        self.assertTrue(result["delivery_evidence_required"])

    def test_no_signing_or_installation_authority(self):
        result = self.build()
        for flag in (
            "source_record_verified",
            "signing_layout_visually_approved",
            "send_authorized",
            "provider_signature_verified",
            "document_retention_verified",
            "legal_eligibility_verified",
            "installation_authorized",
        ):
            self.assertIs(result[flag], False)

    def test_unverified_positions_remain_explicitly_blocked(self):
        result = self.build()
        self.assertIn("sow_manager_signature", result["unplaced_fields"])
        self.assertIn("expedited_customer_reason", result["unplaced_fields"])
        self.assertIn("expedited_comptroller_date", result["unplaced_fields"])

    def test_same_person_cannot_be_manager_and_comptroller(self):
        self.data["identities"]["COMPTROLLER"] = deepcopy(
            self.data["identities"]["INSTALLATION_MANAGER"]
        )
        with self.assertRaises(ValueError):
            self.build()

    def test_missing_customer_identity_rejected(self):
        del self.data["identities"]["CUSTOMER"]
        with self.assertRaises(ValueError):
            self.build()

    def test_invalid_msr_version_rejected(self):
        self.data["msr_version"] = 0
        with self.assertRaises(ValueError):
            self.build()

    def test_invalid_msr_snapshot_hash_rejected(self):
        self.data["snapshot_sha256"] = "not-a-hash"
        with self.assertRaises(ValueError):
            self.build()

    def test_invalid_installation_date_rejected(self):
        self.data["proposed_date"] = "tomorrow"
        with self.assertRaises(ValueError):
            self.build()
