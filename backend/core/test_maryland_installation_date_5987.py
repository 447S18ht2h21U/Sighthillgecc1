"""Focused integration tests for Maryland installation dates."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from .maryland_cancellation_calendar_5983 import (
    EASTERN,
    ADULT_UNDER_65,
    AGE_65_OR_OLDER,
)

from .maryland_installation_date_5987 import (
    assess_maryland_installation_date,
)


MODULE = "core.maryland_installation_date_5987"


class MarylandInstallationDateTests5987(SimpleTestCase):

    def setUp(self):
        self.signed = datetime(
            2026, 11, 30, 14, 0,
            tzinfo=EASTERN,
        )

        self.deadline = datetime(
            2026, 12, 6, 0, 0,
            tzinfo=EASTERN,
        )

        self.msr = SimpleNamespace(
            status="APPROVED",
            snapshot={
                "project_state": "MD",
                "customer_age_category": ADULT_UNDER_65,
                "customer_age_verified_by": str(uuid4()),
                "customer_age_verified_at":
                    "2026-11-30T10:00:00-05:00",
            },
        )

        self.project = SimpleNamespace(
            current_approved=self.msr
        )

    def assess(self):
        with patch(
            MODULE + ".verified_signature_time",
            return_value=self.signed,
        ), patch(
            MODULE + ".cancellation_deadline",
            return_value=self.deadline,
        ):
            return assess_maryland_installation_date(
                self.project
            )

    def test_five_day_provisional_calculation(self):
        result = self.assess()

        self.assertEqual(result["status"], "PROVISIONAL")
        self.assertEqual(
            result["provisional_earliest_installation_date"],
            "2026-12-06",
        )

        self.assertEqual(
            result["required_business_days"], 5
        )

        self.assertIsNone(
            result["earliest_normal_installation_date"]
        )

    def test_seven_day_provisional_calculation(self):
        self.msr.snapshot[
            "customer_age_category"
        ] = AGE_65_OR_OLDER

        result = self.assess()

        self.assertEqual(
            result["provisional_earliest_installation_date"],
            "2026-12-09",
        )

        self.assertEqual(
            result["required_business_days"], 7
        )

    def test_later_verified_deadline_preserved(self):
        self.deadline = datetime(
            2026, 12, 12, 0, 0,
            tzinfo=EASTERN,
        )

        result = self.assess()

        self.assertEqual(
            result["provisional_earliest_installation_date"],
            "2026-12-12",
        )

    def test_missing_approved_msr(self):
        self.project.current_approved = None

        result = self.assess()

        self.assertEqual(
            result["status"], "NOT_ESTABLISHED"
        )

    def test_missing_age_category(self):
        self.msr.snapshot.pop(
            "customer_age_category"
        )

        result = self.assess()

        self.assertEqual(
            result["status"], "NOT_ESTABLISHED"
        )

    def test_unknown_jurisdiction(self):
        self.msr.snapshot["project_state"] = ""

        result = self.assess()

        self.assertEqual(
            result["status"], "NOT_ESTABLISHED"
        )

    def test_unverified_signature_blocks_calculation(self):
        with patch(
            MODULE + ".verified_signature_time",
            side_effect=ValidationError(
                "Authenticated signature required."
            ),
        ):
            result = assess_maryland_installation_date(
                self.project
            )

        self.assertEqual(
            result["status"], "NOT_ESTABLISHED"
        )

        self.assertIsNone(result["contract_signed_at"])

    def test_unverified_deadline_blocks_calculation(self):
        with patch(
            MODULE + ".verified_signature_time",
            return_value=self.signed,
        ), patch(
            MODULE + ".cancellation_deadline",
            side_effect=ValidationError(
                "Verified cancellation deadline required."
            ),
        ):
            result = assess_maryland_installation_date(
                self.project
            )

        self.assertEqual(
            result["status"], "NOT_ESTABLISHED"
        )

    def test_age_verification_after_signing_rejected(self):
        self.msr.snapshot["customer_age_verified_at"] = (
            "2026-11-30T15:00:00-05:00"
        )

        result = self.assess()

        self.assertEqual(
            result["status"], "NOT_ESTABLISHED"
        )

    def test_earlier_age_verification_requires_reconfirmation(self):
        self.msr.snapshot["customer_age_verified_at"] = (
            "2026-11-29T10:00:00-05:00"
        )

        result = self.assess()

        self.assertEqual(
            result["status"], "NOT_ESTABLISHED"
        )

    def test_provisional_result_cannot_authorize_installation(self):
        result = self.assess()

        self.assertFalse(
            result["installation_authorized"]
        )

        self.assertFalse(
            result["expedited_authorized"]
        )

        self.assertIsNone(
            result["earliest_normal_installation_date"]
        )

        self.assertIsNone(
            result["effective_cancellation_deadline"]
        )

    def test_legal_transaction_date_not_assumed(self):
        result = self.assess()

        self.assertIsNone(result["transaction_date"])

        self.assertTrue(result["blocking_reasons"])
