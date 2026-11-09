"""Disposable database tests for an unregistered start-policy preview."""
from datetime import date

from django.test import TestCase, override_settings
from django.utils import timezone

from . import test_installation_schedule as schedule_fixture
from .models import InstallationSchedule
from .installation_three_stage_preview import preview_pre_installation
from .installation_consolidated_preview import preview_consolidated_installation
from .installation_start_policy_preview import preview_installation_start


@override_settings(DEBUG=True, ENVIRONMENT="development")
class InstallationStartDatabaseIntegrationTests(TestCase):
    def setUp(self):
        fixture = schedule_fixture.InstallationScheduleTests()
        fixture.setUp()
        self.fixture = fixture
        self.project = fixture.project

    def make_schedule(self, status="SCHEDULED"):
        self.fixture.make_installation_eligible()
        self.project.refresh_from_db()
        return InstallationSchedule.objects.create(
            project=self.project,
            scheduled_date=timezone.localdate(),
            installation_manager=self.fixture.manager,
            scheduled_by=self.fixture.manager,
            status=status,
        )

    def assess(self, schedule, *, trusted=False):
        stage_one = preview_pre_installation(self.project)
        return preview_installation_start(
            schedule_status=schedule.status,
            stage_one_candidate=stage_one.requirements_satisfied,
            stage_two_candidate=False,
            trusted_equipment_evidence=trusted,
        )

    def test_actual_scheduled_record_is_not_a_start(self):
        schedule = self.make_schedule()
        result = self.assess(schedule)
        self.assertTrue(result.schedule_exists)
        self.assertTrue(result.stage_one_candidate)
        self.assertFalse(result.stage_two_candidate)
        self.assertFalse(result.ready_to_start)
        self.assertFalse(result.start_authorized)
        self.assertFalse(result.installation_started)

    def test_cancelled_schedule_cannot_start(self):
        schedule = self.make_schedule(status="CANCELLED")
        result = self.assess(schedule)
        self.assertFalse(result.schedule_exists)
        self.assertFalse(result.start_authorized)

    def test_completed_schedule_cannot_restart(self):
        schedule = self.make_schedule(status="COMPLETED")
        result = self.assess(schedule)
        self.assertFalse(result.schedule_exists)
        self.assertFalse(result.installation_started)

    def test_missing_approved_msr_blocks_stage_one(self):
        schedule = InstallationSchedule.objects.create(
            project=self.project,
            scheduled_date=date(2026, 11, 2),
            installation_manager=self.fixture.manager,
            scheduled_by=self.fixture.manager,
            status="SCHEDULED",
        )
        result = self.assess(schedule)
        self.assertFalse(result.stage_one_candidate)
        self.assertFalse(result.start_authorized)

    def test_forged_trusted_flag_still_denies_start(self):
        schedule = self.make_schedule()
        result = self.assess(schedule, trusted=True)
        self.assertFalse(result.ready_to_start)
        self.assertFalse(result.start_authorized)
        self.assertFalse(result.installation_started)

    def test_database_consolidated_preview_never_grants_start(self):
        schedule = self.make_schedule()
        assessment = preview_consolidated_installation(
            project_id=self.project.pk,
            installation_starts_at=timezone.now(),
        )
        result = preview_installation_start(
            schedule_status=schedule.status,
            stage_one_candidate=assessment.stage_one_candidate,
            stage_two_candidate=assessment.stage_two_candidate,
            trusted_equipment_evidence=assessment.trusted_installation_evidence,
        )
        self.assertFalse(assessment.scheduling_authorized)
        self.assertFalse(assessment.installation_authorized)
        self.assertFalse(result.ready_to_start)
        self.assertFalse(result.start_authorized)
        self.assertFalse(result.installation_started)
