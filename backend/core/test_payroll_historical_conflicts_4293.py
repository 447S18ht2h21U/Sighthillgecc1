"""Fail-closed historical payroll conflict regression tests."""
from datetime import date

from django.test import SimpleTestCase

from .models import Role
from .payroll_historical_conflicts_4293 import (
    candidate_unambiguous_historical_role,
    historical_conflict_resolution_grants_access,
)


EARNED = date(2026, 10, 12)


def technical():
    return {
        "source_kind": "PROJECT_TECHNICAL_ASSIGNMENT_SNAPSHOT",
        "subject_role": Role.TECHNICIAN,
        "subject_id": "person-a",
        "project_id": "project-a",
        "evidence_reference": "historical-assignment-a",
        "effective_date": date(2026, 10, 1),
        "ended_date": None,
    }


def sales():
    return {
        **technical(),
        "source_kind": "PROJECT_SALES_OWNERSHIP_SNAPSHOT",
        "subject_role": Role.SALES_ASSOCIATE,
        "evidence_reference": "historical-sales-a",
    }


def classify(records):
    return candidate_unambiguous_historical_role(
        records,
        subject_id="person-a",
        project_id="project-a",
        earned_on=EARNED,
    )


class PayrollHistoricalConflicts4293Tests(SimpleTestCase):
    def test_single_matching_technical_candidate(self):
        self.assertEqual(classify([technical()]), Role.TECHNICIAN)
        self.assertFalse(historical_conflict_resolution_grants_access())

    def test_single_matching_sales_candidate(self):
        self.assertEqual(classify([sales()]), Role.SALES_ASSOCIATE)
        self.assertFalse(historical_conflict_resolution_grants_access())

    def test_missing_evidence_is_denied(self):
        for records in ([], None, {}, "TECHNICIAN"):
            with self.subTest(records=records):
                self.assertIsNone(classify(records))

    def test_cross_department_conflict_is_denied(self):
        self.assertIsNone(classify([technical(), sales()]))
        self.assertFalse(historical_conflict_resolution_grants_access(
            evidence_records=[technical(), sales()]
        ))

    def test_duplicate_evidence_is_denied(self):
        first = technical()
        self.assertIsNone(classify([first, dict(first)]))

    def test_two_same_category_claims_are_not_silently_selected(self):
        first = technical()
        second = {
            **first,
            "evidence_reference": "historical-assignment-b",
        }
        self.assertIsNone(classify([first, second]))

    def test_invalid_second_claim_cannot_be_ignored(self):
        bad = {
            **technical(),
            "subject_id": "person-b",
        }
        self.assertIsNone(classify([technical(), bad]))
        self.assertIsNone(classify([bad, technical()]))

    def test_single_mismatched_or_out_of_period_claim_is_denied(self):
        wrong_person = {
            **technical(),
            "subject_id": "person-b",
        }
        ended = {
            **technical(),
            "ended_date": date(2026, 10, 11),
        }
        future = {
            **technical(),
            "effective_date": date(2026, 10, 13),
        }
        for claim in (wrong_person, ended, future):
            with self.subTest(claim=claim):
                self.assertIsNone(classify([claim]))

    def test_candidate_does_not_activate_live_visibility(self):
        for claims in (
            [technical()],
            [sales()],
            [technical(), sales()],
            [],
        ):
            self.assertFalse(
                historical_conflict_resolution_grants_access(
                    evidence_records=claims,
                    viewer_role=Role.COMPTROLLER,
                    historical_binding_verified=True,
                )
            )