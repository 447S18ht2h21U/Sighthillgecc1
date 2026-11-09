"""Pure structural checks: never issue serial-number exceptions."""
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from core.equipment_serial_exception_policy import (
    review_serial_exception,
)

MSR = "11111111-1111-4111-8111-111111111111"
REQUESTER = "22222222-2222-4222-8222-222222222222"
COMPTROLLER = "33333333-3333-4333-8333-333333333333"
REQUESTED = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)


class SerialExceptionPolicyTests(unittest.TestCase):
    def assess(self, **changes):
        values = dict(
            msr_id=MSR,
            unit_id="ROW-001-UNIT-001",
            expected_unit_ids=("ROW-001-UNIT-001", "ROW-001-UNIT-002"),
            requester_id=REQUESTER,
            requester_role="INSTALLATION_MANAGER",
            requester_active=True,
            comptroller_id=COMPTROLLER,
            comptroller_role="COMPTROLLER",
            comptroller_active=True,
            reason="Manufacturer confirms this unit has no serial identifier.",
            genuinely_not_applicable=True,
            requested_at=REQUESTED,
            reviewed_at=REQUESTED + timedelta(hours=1),
        )
        values.update(changes)
        return review_serial_exception(**values)

    def test_valid_candidate_still_not_approved(self):
        result = self.assess()
        self.assertTrue(result.candidate_valid)
        self.assertFalse(result.comptroller_approval_verified)
        self.assertFalse(result.exception_effective)
        self.assertFalse(result.installation_authorized)

    def test_wrong_unit_rejected(self):
        self.assertFalse(
            self.assess(unit_id="ROW-009-UNIT-001").candidate_valid
        )

    def test_inactive_requester_rejected(self):
        self.assertFalse(
            self.assess(requester_active=False).candidate_valid
        )

    def test_unauthorized_requester_rejected(self):
        self.assertFalse(
            self.assess(requester_role="SALES_ASSOCIATE").candidate_valid
        )

    def test_inactive_comptroller_rejected(self):
        self.assertFalse(
            self.assess(comptroller_active=False).candidate_valid
        )

    def test_wrong_reviewer_role_rejected(self):
        self.assertFalse(
            self.assess(comptroller_role="CEO").candidate_valid
        )

    def test_self_review_rejected(self):
        self.assertFalse(
            self.assess(comptroller_id=REQUESTER).candidate_valid
        )

    def test_missing_or_weak_reason_rejected(self):
        for reason in ("", " ", "No serial"):
            with self.subTest(reason=reason):
                self.assertFalse(self.assess(reason=reason).candidate_valid)

    def test_claim_without_non_applicability_rejected(self):
        for value in (False, None, "true", 1):
            with self.subTest(value=value):
                self.assertFalse(
                    self.assess(genuinely_not_applicable=value).candidate_valid
                )

    def test_review_before_request_rejected(self):
        result = self.assess(
            reviewed_at=REQUESTED - timedelta(seconds=1)
        )
        self.assertFalse(result.candidate_valid)

    def test_invalid_identifiers_and_times_rejected(self):
        with self.assertRaises(ValueError):
            self.assess(msr_id="invalid")
        with self.assertRaises(ValueError):
            self.assess(requester_id="invalid")
        with self.assertRaises(ValueError):
            self.assess(expected_unit_ids=("A", "A"))
        with self.assertRaises(ValueError):
            self.assess(reviewed_at=REQUESTED.replace(tzinfo=None))

    def test_results_are_immutable_and_version_scoped(self):
        original = self.assess()
        revised = self.assess(msr_id=str(uuid4()))
        self.assertNotEqual(original.msr_id, revised.msr_id)
        with self.assertRaises(FrozenInstanceError):
            original.exception_effective = True


if __name__ == "__main__":
    unittest.main()