"""Focused tests for authoritative schedule and unified report binding."""
from datetime import datetime, date, timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from .installation_database_schedule_readiness import (
    assess_database_schedule,
    preview_readiness_with_database_schedule,
)


class DatabaseScheduleReadinessTests(TestCase):
    def setUp(self):
        self.project_id = str(uuid4())
        self.start = datetime(
            2026, 11, 4, 15, 0, tzinfo=timezone.utc
        )
        self.manager = SimpleNamespace(
            role="INSTALLATION_MANAGER",
            is_active=True,
        )
        self.scheduler = SimpleNamespace(is_active=True)
        self.record = SimpleNamespace(
            pk=uuid4(),
            status="SCHEDULED",
            scheduled_date=date(2026, 11, 4),
            completed_at=None,
            cancelled_at=None,
            installation_manager=self.manager,
            scheduled_by=self.scheduler,
        )

    def assess(self, rows):
        with patch(
            "core.installation_database_schedule_readiness.InstallationSchedule"
        ) as schedule:
            schedule.Status.SCHEDULED = "SCHEDULED"
            schedule.objects.select_related.return_value.filter.return_value = rows
            result = assess_database_schedule(
                project_id=self.project_id,
                installation_starts_at=self.start,
            )
            schedule.objects.select_related.assert_called_once()
            schedule.objects.select_related.return_value.filter.assert_called_once_with(
                project_id=self.project_id
            )
            return result

    def test_matching_real_record_shape_is_verified_but_untrusted(self):
        result = self.assess([self.record])
        self.assertTrue(result.schedule_verified)
        self.assertEqual(result.schedule_id, str(self.record.pk))
        self.assertFalse(result.installation_authorized)

    def test_missing_or_conflicting_schedules_are_denied(self):
        for rows in ([], [self.record, self.record]):
            result = self.assess(rows)
            self.assertFalse(result.schedule_verified)
            self.assertFalse(result.installation_authorized)

    def test_cancelled_and_mismatched_schedule_denied(self):
        for record in (
            SimpleNamespace(**{
                **vars(self.record),
                "status": "CANCELLED",
            }),
            SimpleNamespace(**{
                **vars(self.record),
                "scheduled_date": date(2026, 11, 5),
            }),
        ):
            result = self.assess([record])
            self.assertFalse(result.schedule_verified)

    def test_inactive_manager_and_scheduler_denied(self):
        for record in (
            SimpleNamespace(**{
                **vars(self.record),
                "installation_manager": SimpleNamespace(
                    role="INSTALLATION_MANAGER", is_active=False
                ),
            }),
            SimpleNamespace(**{
                **vars(self.record),
                "scheduled_by": SimpleNamespace(is_active=False),
            }),
        ):
            result = self.assess([record])
            self.assertFalse(result.schedule_verified)

    def test_verified_database_schedule_cannot_authorize_start(self):
        readiness = SimpleNamespace(
            reviewed_candidate_complete=True,
            blockers=(
                "Database-verified installation schedule is required.",
                "Operational installation-start authority is not implemented.",
            ),
        )
        scheduling = SimpleNamespace(
            schedule_verified=True,
            blockers=(),
        )
        with patch(
            "core.installation_database_schedule_readiness.preview_unified_installation_readiness",
            return_value=readiness,
        ) as report, patch(
            "core.installation_database_schedule_readiness.assess_database_schedule",
            return_value=scheduling,
        ) as database:
            result = preview_readiness_with_database_schedule(
                project_id=self.project_id,
                installation_starts_at=self.start,
            )
            self.assertTrue(result.report_complete_for_review)
            self.assertFalse(result.trusted_installation_evidence)
            self.assertFalse(result.ready_to_start)
            self.assertFalse(result.installation_authorized)
            self.assertFalse(result.installation_started)
            self.assertFalse(any(
                "Database-verified installation schedule is required." == reason
                for reason in result.blockers
            ))
            report.assert_called_once()
            database.assert_called_once()