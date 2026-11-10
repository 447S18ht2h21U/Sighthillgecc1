from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from .installation_future_date_policy_4565 import (
    assess_future_installation_date,
)
from .installation_waiting_period_policy import (
    assess_waiting_period,
)

EASTERN = ZoneInfo("America/New_York")


class WaitingPeriodConsistency4566Tests(SimpleTestCase):

    def check(self, signed, deadline, current):
        return assess_waiting_period(
            verified_contract_signed_at=signed,
            verified_cancellation_deadline=deadline,
            now=current,
        )

    def test_fifth_calendar_day_starts_at_midnight(self):
        signed = datetime(2026, 11, 9, 15, 0, tzinfo=EASTERN)
        deadline = datetime(2026, 11, 12, 9, 0, tzinfo=EASTERN)
        before = datetime(2026, 11, 13, 23, 59, tzinfo=EASTERN)
        start = datetime(2026, 11, 14, 0, 0, tzinfo=EASTERN)
        self.assertFalse(self.check(signed, deadline, before).ready)
        result = self.check(signed, deadline, start)
        self.assertTrue(result.ready)
        self.assertEqual(result.earliest_at, start)

    def test_spring_daylight_saving_transition(self):
        signed = datetime(2026, 3, 6, 15, 0, tzinfo=EASTERN)
        deadline = datetime(2026, 3, 8, 23, 0, tzinfo=EASTERN)
        start = datetime(2026, 3, 11, 0, 0, tzinfo=EASTERN)
        self.assertTrue(self.check(signed, deadline, start).ready)

    def test_fall_daylight_saving_transition(self):
        signed = datetime(2026, 10, 30, 14, 0, tzinfo=EASTERN)
        deadline = datetime(2026, 11, 1, 22, 0, tzinfo=EASTERN)
        start = datetime(2026, 11, 4, 0, 0, tzinfo=EASTERN)
        self.assertTrue(self.check(signed, deadline, start).ready)

    def test_later_verified_cancellation_deadline_controls(self):
        signed = datetime(2026, 11, 9, 15, 0, tzinfo=EASTERN)
        deadline = datetime(2026, 11, 16, 13, 30, tzinfo=EASTERN)
        before = deadline - timedelta(minutes=1)
        self.assertFalse(self.check(signed, deadline, before).ready)
        self.assertTrue(self.check(signed, deadline, deadline).ready)

    def test_future_scheduling_agrees_with_normal_eligibility(self):
        signed = datetime(2026, 11, 9, 15, 0, tzinfo=EASTERN)
        deadline = datetime(2026, 11, 12, 9, 0, tzinfo=EASTERN)
        now = datetime(2026, 11, 9, 16, 0, tzinfo=EASTERN)

        allowed = assess_future_installation_date(
            proposed_date=date(2026, 11, 14),
            verified_contract_signed_at=signed,
            verified_cancellation_deadline=deadline,
            now=now,
        )
        rejected = assess_future_installation_date(
            proposed_date=date(2026, 11, 13),
            verified_contract_signed_at=signed,
            verified_cancellation_deadline=deadline,
            now=now,
        )
        self.assertTrue(allowed["normal_date_eligible"])
        self.assertFalse(rejected["normal_date_eligible"])
        self.assertFalse(allowed["installation_authorized"])
        self.assertFalse(allowed["expedited_authorized"])
