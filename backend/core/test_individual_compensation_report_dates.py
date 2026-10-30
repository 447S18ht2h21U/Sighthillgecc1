"""Tests for individual compensation report calendar date validation."""

from datetime import date, datetime, timezone

from django.test import SimpleTestCase
from rest_framework.exceptions import ValidationError

from .individual_compensation_report_dates import (
    validate_individual_report_dates,
)


class IndividualCompensationReportDateTests(SimpleTestCase):
    def test_valid_iso_date_strings(self):
        result = validate_individual_report_dates(
            "2026-10-01", "2026-10-31"
        )
        self.assertEqual(
            result,
            (date(2026, 10, 1), date(2026, 10, 31)),
        )

    def test_native_date_objects(self):
        start = date(2026, 10, 1)
        end = date(2026, 10, 31)
        self.assertEqual(
            validate_individual_report_dates(start, end),
            (start, end),
        )

    def test_same_day_range_allowed(self):
        day = date(2026, 10, 26)
        self.assertEqual(
            validate_individual_report_dates(day, day),
            (day, day),
        )

    def test_leap_day_allowed(self):
        self.assertEqual(
            validate_individual_report_dates(
                "2024-02-29", "2024-02-29"
            ),
            (date(2024, 2, 29), date(2024, 2, 29)),
        )

    def test_reversed_range_rejected(self):
        with self.assertRaises(ValidationError):
            validate_individual_report_dates(
                "2026-10-31", "2026-10-01"
            )

    def test_missing_start_rejected(self):
        with self.assertRaises(ValidationError):
            validate_individual_report_dates(
                None, "2026-10-31"
            )

    def test_missing_end_rejected(self):
        with self.assertRaises(ValidationError):
            validate_individual_report_dates(
                "2026-10-01", None
            )

    def test_invalid_calendar_day_rejected(self):
        with self.assertRaises(ValidationError):
            validate_individual_report_dates(
                "2026-02-29", "2026-03-01"
            )

    def test_non_iso_format_rejected(self):
        with self.assertRaises(ValidationError):
            validate_individual_report_dates(
                "10/01/2026", "10/31/2026"
            )

    def test_datetime_values_rejected(self):
        timestamp = datetime(
            2026, 10, 1, 12, 30, tzinfo=timezone.utc
        )
        with self.assertRaises(ValidationError):
            validate_individual_report_dates(
                timestamp, date(2026, 10, 31)
            )

    def test_timestamp_string_rejected(self):
        with self.assertRaises(ValidationError):
            validate_individual_report_dates(
                "2026-10-01T12:30:00Z",
                "2026-10-31",
            )

    def test_non_ascii_digits_rejected(self):
        with self.assertRaises(ValidationError):
            validate_individual_report_dates(
                "٢٠٢٦-10-01",
                "2026-10-31",
            )