"""Real database scheduling safeguards and readiness integration."""
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone

from . import test_installation_combined_real_evidence as fixture_module
from .installation_database_schedule_readiness import (
    assess_database_schedule,
    preview_readiness_with_database_schedule,
)
from .models import InstallationSchedule


EASTERN = ZoneInfo("America/New_York")


@override_settings(DEBUG=True, ENVIRONMENT="development")
class RealInstallationScheduleReadinessTests(TestCase):
    def setUp(self):
        fixture = fixture_module.RealTwoStageDatabaseRegressionTests()
        fixture.setUp()
        self.fixture = fixture
        self.msr = fixture.prepare()
        self.project = fixture.project
        self.manager = fixture.installation_manager
        self.project_id = str(self.project.pk)

        self.assertFalse(
            InstallationSchedule.objects.filter(
                project=self.project
            ).exists(),
            "Fixture must start without an installation schedule.",
        )

        self.day = (
            timezone.localtime(timezone.now(), EASTERN).date()
            + timedelta(days=30)
        )
        self.start = datetime.combine(
            self.day, time(10, 0), tzinfo=EASTERN
        )

    def create_schedule(self, **changes):
        values = {
            "project": self.project,
            "scheduled_date": self.day,
            "status": InstallationSchedule.Status.SCHEDULED,
            "installation_manager": self.manager,
            "scheduled_by": self.manager,
        }
        values.update(changes)
        return InstallationSchedule.objects.create(**values)

    def verify(self):
        return assess_database_schedule(
            project_id=self.project_id,
            installation_starts_at=self.start,
        )

    def test_real_schedule_integrates_without_authorizing(self):
        record = self.create_schedule()
        assessment = self.verify()
        self.assertTrue(assessment.schedule_verified, assessment.blockers)
        self.assertEqual(assessment.schedule_id, str(record.pk))
        self.assertEqual(assessment.scheduled_date, self.day.isoformat())
        self.assertFalse(assessment.installation_authorized)

        report = preview_readiness_with_database_schedule(
            project_id=self.project_id,
            installation_starts_at=self.start,
            now=self.start - timedelta(hours=1),
        )
        self.assertTrue(report.scheduling.schedule_verified)
        self.assertEqual(report.scheduling.schedule_id, str(record.pk))
        self.assertFalse(report.trusted_installation_evidence)
        self.assertFalse(report.ready_to_start)
        self.assertFalse(report.installation_authorized)
        self.assertFalse(report.installation_started)

    def test_database_prevents_duplicate_schedule(self):
        original = self.create_schedule()
        self.assertTrue(self.verify().schedule_verified)

        # The nested transaction preserves the outer Django test
        # transaction when the database rejects the duplicate.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_schedule()

        remaining = list(
            InstallationSchedule.objects.filter(project=self.project)
        )
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].pk, original.pk)
        self.assertTrue(self.verify().schedule_verified)
        self.assertFalse(self.verify().installation_authorized)

    def test_cancelled_schedule_cannot_verify(self):
        self.create_schedule(
            status=InstallationSchedule.Status.CANCELLED,
        )
        assessment = self.verify()
        self.assertFalse(assessment.schedule_verified)
        self.assertTrue(assessment.blockers)
        self.assertFalse(assessment.installation_authorized)