"""Database-free contract checks for proposed historical payroll evidence."""
from datetime import date, datetime

from django.test import SimpleTestCase

from .models import Role
from .payroll_historical_evidence_4292 import (
    candidate_historical_role,
    historical_payroll_live_access,
)


EARNED = date(2026, 10, 12)


def evidence(source="PROJECT_TECHNICAL_ASSIGNMENT_SNAPSHOT", **changes):
    value = {
        "source_kind": source,
        "subject_role": Role.TECHNICIAN,
        "subject_id": "person-a",
        "project_id": "project-a",
        "evidence_reference": "history-record-a",
        "effective_date": date(2026, 10, 1),
        "ended_date": None,
    }
    value.update(changes)
    return value


def category(value, *, subject="person-a", project="project-a", earned=EARNED):
    return candidate_historical_role(
        value,
        subject_id=subject,
        project_id=project,
        earned_on=earned,
    )


class HistoricalPayrollEvidence4292Tests(SimpleTestCase):
    def test_matching_technician_candidate(self):
        self.assertEqual(category(evidence()), Role.TECHNICIAN)
        self.assertFalse(historical_payroll_live_access())

    def test_matching_sales_candidate_uses_distinct_source(self):
        item = evidence(
            "PROJECT_SALES_OWNERSHIP_SNAPSHOT",
            subject_role=Role.SALES_ASSOCIATE,
        )
        self.assertEqual(category(item), Role.SALES_ASSOCIATE)
        self.assertFalse(historical_payroll_live_access(item))

    def test_wrong_person_and_project_fail_closed(self):
        self.assertIsNone(category(evidence(), subject="person-b"))
        self.assertIsNone(category(evidence(), project="project-b"))
        self.assertIsNone(category(evidence(subject_id="person-b")))
        self.assertIsNone(category(evidence(project_id="project-b")))

    def test_future_and_ended_assignments_are_rejected(self):
        self.assertIsNone(category(evidence(
            effective_date=date(2026, 10, 13)
        )))
        self.assertIsNone(category(evidence(
            ended_date=date(2026, 10, 11)
        )))
        self.assertIsNone(category(evidence(
            effective_date=date(2026, 10, 10),
            ended_date=date(2026, 10, 9),
        )))

    def test_period_boundaries_are_inclusive_for_candidate_only(self):
        item = evidence(
            effective_date=date(2026, 10, 12),
            ended_date=date(2026, 10, 12),
        )
        self.assertEqual(category(item), Role.TECHNICIAN)
        self.assertFalse(historical_payroll_live_access(item))

    def test_role_code_or_description_is_not_a_source(self):
        for source in (
            "TECHNICIAN",
            "Sales Associate",
            "Installer",
            "",
            None,
        ):
            with self.subTest(source=source):
                self.assertIsNone(category(evidence(source)))

    def test_cross_department_evidence_is_rejected(self):
        self.assertIsNone(category(evidence(
            subject_role=Role.SALES_ASSOCIATE
        )))
        self.assertIsNone(category(evidence(
            "PROJECT_SALES_OWNERSHIP_SNAPSHOT",
            subject_role=Role.TECHNICIAN,
        )))

    def test_missing_extra_and_invalid_fields_are_rejected(self):
        original = evidence()
        for key in original:
            with self.subTest(missing=key):
                value = dict(original)
                del value[key]
                self.assertIsNone(category(value))
        self.assertIsNone(category({**original, "approved": True}))
        self.assertIsNone(category(evidence(evidence_reference="")))
        self.assertIsNone(category(evidence(effective_date="2026-10-01")))
        self.assertIsNone(category(evidence(
            ended_date=datetime(2026, 10, 12)
        )))

    def test_invalid_requested_id_and_date_are_rejected(self):
        self.assertIsNone(category(evidence(), subject=""))
        self.assertIsNone(category(evidence(), project=""))
        self.assertIsNone(category(evidence(), earned=None))
        self.assertIsNone(category(
            evidence(), earned=datetime(2026, 10, 12)
        ))

    def test_no_candidate_can_enable_live_disclosure(self):
        technician = evidence()
        sales = evidence(
            "PROJECT_SALES_OWNERSHIP_SNAPSHOT",
            subject_role=Role.SALES_ASSOCIATE,
        )
        for item in (technician, sales, {}, None):
            with self.subTest(item=item):
                self.assertFalse(historical_payroll_live_access(
                    evidence=item,
                    viewer_role=Role.COMPTROLLER,
                    historical_binding_verified=True,
                ))