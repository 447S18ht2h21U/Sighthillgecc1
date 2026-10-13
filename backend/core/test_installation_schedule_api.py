"""API regression tests for installation scheduling."""

from django.test import TestCase
from rest_framework.test import APIClient

from .models import Customer, InstallationSchedule, Project, Role, User


class InstallationScheduleAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.comptroller = User.objects.create_user(
            username="schedule_api_comptroller",
            password="TestOnlyPassword2026!",
            role=Role.COMPTROLLER,
        )
        self.manager = User.objects.create_user(
            username="schedule_api_manager",
            password="TestOnlyPassword2026!",
            role=Role.INSTALLATION_MANAGER,
        )
        self.customer = Customer.objects.create(
            legal_name="Installation Schedule API Customer",
            billing_address="123 Test Road",
            created_by=self.comptroller,
        )
        self.project = Project.objects.create(
            code="INSTALL-API-001",
            customer=self.customer,
            location="Installation Schedule API Location",
            sales_associate=self.comptroller,
            reviewer=self.comptroller,
            state="APPROVED",
        )

    def test_installation_manager_can_schedule(self):
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            "/api/installation-schedules/",
            {
                "project": str(self.project.pk),
                "scheduled_date": "2026-10-20",
                "installation_manager": str(self.manager.pk),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        schedule = InstallationSchedule.objects.get()
        self.assertEqual(schedule.project_id, self.project.pk)
        self.assertEqual(schedule.installation_manager_id, self.manager.pk)
        self.assertEqual(schedule.scheduled_by_id, self.manager.pk)
        self.assertEqual(
            schedule.status,
            InstallationSchedule.Status.SCHEDULED,
        )
    def test_unauthorized_employee_cannot_schedule(self):
        technician = User.objects.create_user(
            username="schedule_api_unauthorized_technician",
            password="TestOnlyPassword2026!",
            role=Role.TECHNICIAN,
        )
        self.client.force_authenticate(technician)
        response = self.client.post(
            "/api/installation-schedules/",
            {
                "project": str(self.project.pk),
                "scheduled_date": "2026-10-20",
                "installation_manager": str(self.manager.pk),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(InstallationSchedule.objects.exists())

    def test_unauthenticated_user_cannot_schedule(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(
            "/api/installation-schedules/",
            {
                "project": str(self.project.pk),
                "scheduled_date": "2026-10-20",
                "installation_manager": str(self.manager.pk),
            },
            format="json",
        )
        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(InstallationSchedule.objects.exists())

    def test_installation_manager_can_complete_schedule(self):
        from datetime import date
        from .installation_schedule_services import create_installation_schedule

        schedule = create_installation_schedule(
            actor=self.manager,
            project=self.project,
            scheduled_date=date(2026, 10, 20),
            installation_manager=self.manager,
        )
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            f"/api/installation-schedules/{schedule.pk}/complete/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        schedule.refresh_from_db()
        self.assertEqual(schedule.status, InstallationSchedule.Status.COMPLETED)
        self.assertIsNotNone(schedule.completed_at)
        self.assertIsNone(schedule.cancelled_at)
        self.assertEqual(InstallationSchedule.objects.count(), 1)

    def test_installation_manager_can_cancel_schedule(self):
        from datetime import date
        from .installation_schedule_services import create_installation_schedule

        schedule = create_installation_schedule(
            actor=self.manager,
            project=self.project,
            scheduled_date=date(2026, 10, 20),
            installation_manager=self.manager,
        )
        self.client.force_authenticate(self.manager)
        response = self.client.post(
            f"/api/installation-schedules/{schedule.pk}/cancel/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        schedule.refresh_from_db()
        self.assertEqual(schedule.status, InstallationSchedule.Status.CANCELLED)
        self.assertIsNotNone(schedule.cancelled_at)
        self.assertIsNone(schedule.completed_at)
        self.assertEqual(InstallationSchedule.objects.count(), 1)

    def test_unauthorized_employee_cannot_complete_or_cancel(self):
        from datetime import date
        from .installation_schedule_services import create_installation_schedule

        schedule = create_installation_schedule(
            actor=self.manager,
            project=self.project,
            scheduled_date=date(2026, 10, 20),
            installation_manager=self.manager,
        )
        technician = User.objects.create_user(
            username="schedule_api_action_technician",
            password="TestOnlyPassword2026!",
            role=Role.TECHNICIAN,
        )
        self.client.force_authenticate(technician)
        for operation in ("complete", "cancel"):
            with self.subTest(operation=operation):
                response = self.client.post(
                    f"/api/installation-schedules/{schedule.pk}/{operation}/",
                    {},
                    format="json",
                )
                self.assertEqual(response.status_code, 403)
                schedule.refresh_from_db()
                self.assertEqual(schedule.status, InstallationSchedule.Status.SCHEDULED)
                self.assertIsNone(schedule.completed_at)
                self.assertIsNone(schedule.cancelled_at)

    def test_approved_temporary_installation_manager_can_schedule(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import TemporaryDutyActivity
        from .temporary_duty_services import approve_temporary_duty, request_temporary_duty

        temporary_manager = User.objects.create_user(
            username="schedule_api_temporary_ceo",
            password="TestOnlyPassword2026!",
            role=Role.CEO,
        )
        now = timezone.now()
        authorization = request_temporary_duty(
            employee=temporary_manager,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=temporary_manager,
            reason="Temporary installation management coverage",
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=2),
        )
        approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )
        self.client.force_authenticate(temporary_manager)
        response = self.client.post(
            "/api/installation-schedules/",
            {
                "project": str(self.project.pk),
                "scheduled_date": "2026-10-20",
                "installation_manager": str(self.manager.pk),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        schedule = InstallationSchedule.objects.get()
        self.assertEqual(schedule.scheduled_by_id, temporary_manager.pk)
        self.assertTrue(
            TemporaryDutyActivity.objects.filter(
                authorization=authorization,
                employee=temporary_manager,
            ).exists()
        )

    def test_ceo_without_temporary_authorization_cannot_schedule(self):
        ceo = User.objects.create_user(
            username="schedule_api_ceo_without_authorization",
            password="TestOnlyPassword2026!",
            role=Role.CEO,
        )
        self.client.force_authenticate(ceo)
        response = self.client.post(
            "/api/installation-schedules/",
            {
                "project": str(self.project.pk),
                "scheduled_date": "2026-10-20",
                "installation_manager": str(self.manager.pk),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(InstallationSchedule.objects.exists())
