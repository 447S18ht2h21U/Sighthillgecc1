"""Isolated tests of the approved Contract-based waiting calculation."""
import unittest
from datetime import datetime, timedelta, timezone
from dataclasses import FrozenInstanceError

from core.installation_waiting_period_policy import (
    EASTERN, WAITING_DAYS, assess_waiting_period,
)


UTC = timezone.utc


class WaitingPeriodPolicyTests(unittest.TestCase):
    def assess(self, contract=None, cancellation=None, now=None):
        return assess_waiting_period(
            verified_contract_signed_at=contract or
                datetime(2026, 11, 1, 12, tzinfo=UTC),
            verified_cancellation_deadline=cancellation or
                datetime(2026, 11, 4, 12, tzinfo=UTC),
            now=now or datetime(2026, 11, 7, 12, tzinfo=UTC),
        )

    def test_waiting_period_is_five_days(self):
        self.assertEqual(WAITING_DAYS, 5)
        result = self.assess()
        self.assertEqual(
            result.contract_wait_ends_at.date(),
            datetime(2026, 11, 6).date(),
        )

    def test_contract_signature_controls_normal_case(self):
        result = self.assess()
        self.assertEqual(
            result.earliest_at,
            result.contract_wait_ends_at,
        )
        self.assertTrue(result.ready)

    def test_future_cancellation_deadline_controls(self):
        deadline = datetime(2026, 11, 10, 12, tzinfo=UTC)
        result = self.assess(cancellation=deadline)
        self.assertEqual(result.earliest_at, deadline.astimezone(EASTERN))
        self.assertFalse(result.ready)

    def test_one_second_early_is_blocked(self):
        deadline = self.assess().earliest_at
        result = self.assess(
            now=deadline.astimezone(UTC) - timedelta(seconds=1)
        )
        self.assertFalse(result.ready)

    def test_exact_boundary_is_ready(self):
        deadline = self.assess().earliest_at
        result = self.assess(now=deadline)
        self.assertTrue(result.ready)
        self.assertFalse(result.installation_authorized)

    def test_naive_contract_time_is_rejected(self):
        with self.assertRaises(ValueError):
            self.assess(contract=datetime(2026, 11, 1, 12))

    def test_naive_cancellation_time_is_rejected(self):
        with self.assertRaises(ValueError):
            self.assess(cancellation=datetime(2026, 11, 5, 12))

    def test_naive_current_time_is_rejected(self):
        with self.assertRaises(ValueError):
            self.assess(now=datetime(2026, 11, 7, 12))

    def test_spring_daylight_saving_keeps_local_calendar_days(self):
        signed = datetime(2026, 3, 6, 10, tzinfo=EASTERN)
        result = self.assess(
            contract=signed,
            cancellation=datetime(2026, 3, 7, 10, tzinfo=EASTERN),
            now=datetime(2026, 3, 11, 10, tzinfo=EASTERN),
        )
        self.assertEqual(
            (result.contract_wait_ends_at.month,
             result.contract_wait_ends_at.day,
             result.contract_wait_ends_at.hour),
            (3, 11, 10),
        )
        self.assertTrue(result.ready)

    def test_fall_daylight_saving_keeps_local_calendar_days(self):
        signed = datetime(2026, 10, 30, 10, tzinfo=EASTERN)
        result = self.assess(
            contract=signed,
            cancellation=datetime(2026, 10, 31, 10, tzinfo=EASTERN),
            now=datetime(2026, 11, 4, 10, tzinfo=EASTERN),
        )
        self.assertEqual(
            (result.contract_wait_ends_at.month,
             result.contract_wait_ends_at.day,
             result.contract_wait_ends_at.hour),
            (11, 4, 10),
        )
        self.assertTrue(result.ready)

    def test_result_is_immutable_and_not_installation_authority(self):
        result = self.assess()
        self.assertFalse(result.installation_authorized)
        with self.assertRaises(FrozenInstanceError):
            result.ready = False

    def test_missing_and_invalid_inputs_fail_closed(self):
        for value in (None, "", "2026-11-01", 123):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    assess_waiting_period(
                        verified_contract_signed_at=value,
                        verified_cancellation_deadline=datetime(
                            2026, 11, 4, tzinfo=UTC
                        ),
                        now=datetime(2026, 11, 7, tzinfo=UTC),
                    )


if __name__ == "__main__":
    unittest.main()