from datetime import date, datetime, timedelta
from django.test import SimpleTestCase

from .installation_future_date_policy_4565 import assess_future_installation_date
from .installation_waiting_period_policy import EASTERN


class FutureInstallationDate4565Tests(SimpleTestCase):

    def setUp(self):
        self.now = datetime(2026, 11, 9, 9, 0, tzinfo=EASTERN)
        self.signed = self.now - timedelta(days=2)
        self.deadline = self.now + timedelta(days=1)

    def assess(self, day):
        return assess_future_installation_date(
            proposed_date=day,
            verified_contract_signed_at=self.signed,
            verified_cancellation_deadline=self.deadline,
            now=self.now,
        )

    def test_future_date_after_waiting_is_candidate(self):
        result = self.assess(date(2026, 11, 15))
        self.assertTrue(result["normal_date_eligible"])
        self.assertFalse(result["installation_authorized"])

    def test_early_date_remains_blocked(self):
        self.assertFalse(
            self.assess(date(2026, 11, 10))["normal_date_eligible"]
        )

    def test_past_date_rejected(self):
        with self.assertRaises(ValueError):
            self.assess(date(2026, 11, 8))

    def test_scheduling_is_not_expediting(self):
        self.assertFalse(
            self.assess(date(2026, 11, 15))["expedited_authorized"]
        )

    def test_invalid_date_rejected(self):
        with self.assertRaises(ValueError):
            self.assess("2026-11-15")