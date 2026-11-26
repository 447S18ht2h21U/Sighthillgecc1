"""Focused Maryland statutory calendar tests."""

import unittest

from datetime import date, datetime
from zoneinfo import ZoneInfo

from .maryland_cancellation_calendar_5983 import (
    ADULT_UNDER_65,
    AGE_65_OR_OLDER,
    calculate_cancellation_calendar,
    date_after_established_deadlines,
    is_business_day,
    named_holidays,
)


class MarylandCancellationCalendarTests5983(unittest.TestCase):

    def calculate(self, day, age=ADULT_UNDER_65):
        return calculate_cancellation_calendar(
            transaction_date=day,
            age_category=age,
        )

    def test_five_business_days(self):
        result = self.calculate(date(2026, 11, 30))

        self.assertEqual(result["required_business_days"], 5)
        self.assertEqual(
            result["final_cancellation_day"], "2026-12-05"
        )
        self.assertEqual(
            result["earliest_date_after_calculated_deadline"],
            "2026-12-06",
        )
        self.assertFalse(result["installation_authorized"])

    def test_seven_business_days(self):
        result = self.calculate(
            date(2026, 11, 30), AGE_65_OR_OLDER
        )

        self.assertEqual(result["required_business_days"], 7)
        self.assertEqual(
            result["final_cancellation_day"], "2026-12-08"
        )
        self.assertEqual(
            result["earliest_date_after_calculated_deadline"],
            "2026-12-09",
        )

    def test_saturday_counts(self):
        self.assertTrue(is_business_day(date(2026, 12, 5)))

    def test_sunday_excluded(self):
        self.assertFalse(is_business_day(date(2026, 12, 6)))

    def test_transaction_date_not_counted(self):
        result = self.calculate(date(2026, 11, 30))

        self.assertEqual(
            result["counted_business_days"][0], "2026-12-01"
        )

    def test_thanksgiving_excluded(self):
        result = self.calculate(date(2026, 11, 25))

        self.assertIn(
            "2026-11-26", result["excluded_dates"]
        )

        self.assertEqual(
            result["final_cancellation_day"], "2026-12-02"
        )

    def test_nine_named_holidays(self):
        self.assertEqual(
            named_holidays(2026),
            {
                date(2026, 1, 1),
                date(2026, 2, 16),
                date(2026, 5, 25),
                date(2026, 7, 4),
                date(2026, 9, 7),
                date(2026, 10, 12),
                date(2026, 11, 11),
                date(2026, 11, 26),
                date(2026, 12, 25),
            },
        )

    def test_observed_holiday_extension(self):
        self.assertFalse(is_business_day(date(2026, 7, 3)))
        self.assertFalse(is_business_day(date(2026, 7, 4)))

    def test_observed_new_year_crosses_year_boundary(self):
        self.assertFalse(is_business_day(date(2027, 12, 31)))

    def test_christmas_and_new_year_excluded(self):
        result = self.calculate(
            date(2026, 12, 24), AGE_65_OR_OLDER
        )

        self.assertIn(
            "2026-12-25", result["excluded_dates"]
        )

        self.assertIn(
            "2027-01-01", result["excluded_dates"]
        )

    def test_unknown_age_rejected(self):
        for age in ("", None, "UNKNOWN", "UNDER_18"):
            with self.subTest(age=age):
                with self.assertRaises(ValueError):
                    self.calculate(date(2026, 11, 30), age)

    def test_missing_transaction_date_rejected(self):
        with self.assertRaises(ValueError):
            self.calculate(None)

    def test_missing_verified_deadline_rejected(self):
        with self.assertRaises(ValueError):
            date_after_established_deadlines(
                transaction_date=date(2026, 11, 30),
                age_category=ADULT_UNDER_65,
                independently_verified_deadline=None,
            )

    def test_naive_deadline_rejected(self):
        with self.assertRaises(ValueError):
            date_after_established_deadlines(
                transaction_date=date(2026, 11, 30),
                age_category=ADULT_UNDER_65,
                independently_verified_deadline=datetime(
                    2026, 12, 6
                ),
            )

    def test_earlier_deadline_cannot_shorten_protection(self):
        result = date_after_established_deadlines(
            transaction_date=date(2026, 11, 30),
            age_category=AGE_65_OR_OLDER,
            independently_verified_deadline=datetime(
                2026, 12, 6,
                tzinfo=ZoneInfo("America/New_York"),
            ),
        )

        self.assertEqual(
            result["earliest_normal_installation_date"],
            "2026-12-09",
        )

    def test_later_verified_deadline_controls(self):
        result = date_after_established_deadlines(
            transaction_date=date(2026, 11, 30),
            age_category=ADULT_UNDER_65,
            independently_verified_deadline=datetime(
                2026, 12, 10, 15, 30,
                tzinfo=ZoneInfo("America/New_York"),
            ),
        )

        self.assertEqual(
            result["earliest_normal_installation_date"],
            "2026-12-11",
        )

    def test_eastern_daylight_saving_transition(self):
        result = self.calculate(
            date(2026, 10, 30), AGE_65_OR_OLDER
        )

        self.assertTrue(
            result["cancellation_deadline_exclusive"]
                .endswith("-05:00")
        )
