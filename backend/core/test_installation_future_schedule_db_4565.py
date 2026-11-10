from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .installation_schedule_services import create_future_installation_schedule
from .models import InstallationSchedule
from .test_installation_schedule import InstallationScheduleTests


class FutureScheduleDatabase4565Tests(TestCase):
    # Reuse the established fictional project and evidence fixtures.
    setUp = InstallationScheduleTests.setUp
    make_installation_eligible = InstallationScheduleTests.make_installation_eligible

    def future_date(self):
        return timezone.localdate() + timedelta(days=14)

    def test_authorized_future_schedule_persists(self):
        self.make_installation_eligible()
        day = self.future_date()
        schedule = create_future_installation_schedule(
            actor=self.manager,
            project=self.project,
            scheduled_date=day,
            installation_manager=self.manager,
        )
        saved = InstallationSchedule.objects.get(pk=schedule.pk)
        self.assertEqual(saved.scheduled_date, day)
        self.assertEqual(saved.status, InstallationSchedule.Status.SCHEDULED)
        self.assertEqual(saved.scheduled_by_id, self.manager.pk)
        self.assertIsNone(saved.completed_at)

    def test_past_date_does_not_create_schedule(self):
        self.make_installation_eligible()
        before = InstallationSchedule.objects.count()
        with self.assertRaises(ValidationError):
            create_future_installation_schedule(
                actor=self.manager,
                project=self.project,
                scheduled_date=timezone.localdate() - timedelta(days=1),
                installation_manager=self.manager,
            )
        self.assertEqual(InstallationSchedule.objects.count(), before)

    def test_unapproved_msr_does_not_create_schedule(self):
        before = InstallationSchedule.objects.count()
        with self.assertRaises(ValidationError):
            create_future_installation_schedule(
                actor=self.manager,
                project=self.project,
                scheduled_date=self.future_date(),
                installation_manager=self.manager,
            )
        self.assertEqual(InstallationSchedule.objects.count(), before)