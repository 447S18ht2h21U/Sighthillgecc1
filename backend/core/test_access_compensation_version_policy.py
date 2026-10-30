"""Regression tests for nonbinding compensation-version policy."""

from datetime import date, datetime

from django.test import SimpleTestCase

from .access_compensation_version_policy import (
    CompensationVersion,
    compensation_version_access_granted,
    may_self_approve_compensation,
    requires_retroactive_review,
    select_historical_plan,
    validate_effective_date,
    validate_version,
)


class CompensationVersionPolicyTests(SimpleTestCase):

    def setUp(self):
        self.first = CompensationVersion(
            version=1,
            effective_date=date(2026, 1, 1),
            status="APPROVED",
        )
        self.second = CompensationVersion(
            version=2,
            effective_date=date(2026, 4, 1),
            status="APPROVED",
        )

    def test_historical_period_uses_original_version(self):
        result = select_historical_plan(
            [self.first, self.second],
            date(2026, 3, 15),
        )
        self.assertEqual(result, self.first)

    def test_new_rate_applies_from_approved_effective_date(self):
        result = select_historical_plan(
            [self.first, self.second],
            date(2026, 4, 1),
        )
        self.assertEqual(result, self.second)

    def test_no_approved_version_before_earning_date(self):
        result = select_historical_plan(
            [self.first, self.second],
            date(2025, 12, 31),
        )
        self.assertIsNone(result)

    def test_draft_and_superseded_versions_are_excluded(self):
        draft = CompensationVersion(
            version=3,
            effective_date=date(2026, 5, 1),
            status="DRAFT",
        )
        superseded = CompensationVersion(
            version=4,
            effective_date=date(2026, 6, 1),
            status="SUPERSEDED",
        )
        result = select_historical_plan(
            [self.first, self.second, draft, superseded],
            date(2026, 7, 1),
        )
        self.assertEqual(result, self.second)

    def test_duplicate_approved_effective_dates_are_rejected(self):
        duplicate = CompensationVersion(
            version=3,
            effective_date=date(2026, 4, 1),
            status="APPROVED",
        )
        with self.assertRaises(ValueError):
            select_historical_plan(
                [self.first, self.second, duplicate],
                date(2026, 2, 1),
            )

    def test_invalid_versions_are_rejected(self):
        for value in (0, -1, True, "2", 1.5):
            with self.subTest(value=value):
                self.assertFalse(validate_version(value))

        invalid = CompensationVersion(
            version=0,
            effective_date=date(2026, 1, 1),
            status="APPROVED",
        )
        with self.assertRaises(ValueError):
            select_historical_plan(
                [invalid],
                date(2026, 1, 1),
            )

    def test_invalid_effective_dates_are_rejected(self):
        self.assertFalse(validate_effective_date("2026-01-01"))
        self.assertFalse(validate_effective_date(datetime(2026, 1, 1)))
        with self.assertRaises(ValueError):
            select_historical_plan(
                [self.first],
                "2026-03-01",
            )

    def test_retroactive_review_boundary(self):
        processed = date(2026, 3, 31)
        self.assertTrue(
            requires_retroactive_review(
                date(2026, 3, 31), processed
            )
        )
        self.assertTrue(
            requires_retroactive_review(
                date(2026, 3, 1), processed
            )
        )
        self.assertFalse(
            requires_retroactive_review(
                date(2026, 4, 1), processed
            )
        )

    def test_self_approval_and_automatic_permissions_denied(self):
        self.assertFalse(may_self_approve_compensation())
        self.assertFalse(compensation_version_access_granted())
