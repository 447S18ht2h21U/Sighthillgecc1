"""Pure tests for inclusive compensation-period overlap."""

from datetime import date, datetime, timezone

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from .individual_compensation_report_periods import (
    compensation_period_filter_bounds,
    compensation_period_overlaps,
)


class IndividualCompensationPeriodTests(SimpleTestCase):
    def test_identical_periods_overlap(self):
        self.assertTrue(
            compensation_period_overlaps(
                "2026-10-01", "2026-10-15",
                "2026-10-01", "2026-10-15",
            )
        )

    def test_report_entirely_inside_payment_period(self):
        self.assertTrue(
            compensation_period_overlaps(
                "2026-10-01", "2026-10-15",
                "2026-10-10", "2026-10-12",
            )
        )

    def test_payment_entirely_inside_report_period(self):
        self.assertTrue(
            compensation_period_overlaps(
                "2026-10-10", "2026-10-12",
                "2026-10-01", "2026-10-31",
            )
        )

    def test_first_day_boundary_is_inclusive(self):
        self.assertTrue(
            compensation_period_overlaps(
                "2026-10-01", "2026-10-15",
                "2026-09-20", "2026-10-01",
            )
        )

    def test_last_day_boundary_is_inclusive(self):
        self.assertTrue(
            compensation_period_overlaps(
                "2026-10-01", "2026-10-15",
                "2026-10-15", "2026-10-31",
            )
        )

    def test_period_before_report_does_not_overlap(self):
        self.assertFalse(
            compensation_period_overlaps(
                "2026-09-01", "2026-09-15",
                "2026-10-01", "2026-10-31",
            )
        )

    def test_period_after_report_does_not_overlap(self):
        self.assertFalse(
            compensation_period_overlaps(
                "2026-11-01", "2026-11-15",
                "2026-10-01", "2026-10-31",
            )
        )

    def test_single_day_payment_and_report_overlap(self):
        self.assertTrue(
            compensation_period_overlaps(
                date(2026, 10, 26), date(2026, 10, 26),
                date(2026, 10, 26), date(2026, 10, 26),
            )
        )

    def test_reversed_payment_period_rejected(self):
        with self.assertRaises(ValidationError):
            compensation_period_overlaps(
                "2026-10-15", "2026-10-01",
                "2026-10-01", "2026-10-31",
            )

    def test_reversed_report_period_rejected(self):
        with self.assertRaises(ValidationError):
            compensation_period_overlaps(
                "2026-10-01", "2026-10-15",
                "2026-10-31", "2026-10-01",
            )

    def test_datetime_is_rejected(self):
        with self.assertRaises(ValidationError):
            compensation_period_overlaps(
                datetime(2026, 10, 1, tzinfo=timezone.utc),
                date(2026, 10, 15),
                date(2026, 10, 1),
                date(2026, 10, 31),
            )

    def test_query_filter_bounds_are_inclusive(self):
        self.assertEqual(
            compensation_period_filter_bounds(
                "2026-10-01", "2026-10-31"
            ),
            {
                "period_start_on_or_before": date(2026, 10, 31),
                "period_end_on_or_after": date(2026, 10, 1),
            },
        )