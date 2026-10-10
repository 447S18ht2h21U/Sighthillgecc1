from datetime import date

from django.test import TestCase

from .models import (
    Project,
    Customer,
    User,
    Role,
    InstallationSchedule,
)

from .installation_schedule_services import (
    create_installation_schedule,
    complete_installation_schedule,
    cancel_installation_schedule,
)


class InstallationScheduleTests(TestCase):

    def setUp(self):

        self.manager = User.objects.create_user(
            username='installation_manager_test',
            password='test-password',
            role=Role.INSTALLATION_MANAGER,
            initials='IM',
        )

        self.comptroller = User.objects.create_user(
            username='installation_comptroller_test',
            password='test-password',
            role=Role.COMPTROLLER,
            initials='CC',
        )

        self.customer = Customer.objects.create(
            legal_name='Installation Test Customer',
            billing_address='123 Installation Road',
            created_by=self.comptroller,
        )

        self.project = Project.objects.create(
            code='INSTALL-TEST-001',
            customer=self.customer,
            location='Installation Test Location',
            sales_associate=self.comptroller,
            reviewer=self.comptroller,
            state='APPROVED',
        )

    def test_installation_can_be_scheduled(self):

        schedule = create_installation_schedule(
            self.manager,
            self.project,
            date(2026, 10, 20),
            self.manager,
        )

        self.assertEqual(
            schedule.status,
            InstallationSchedule.Status.SCHEDULED,
        )

        self.assertEqual(
            schedule.project,
            self.project,
        )

        self.assertEqual(
            schedule.installation_manager,
            self.manager,
        )

    def test_installation_can_be_completed(self):

        schedule = create_installation_schedule(
            self.manager,
            self.project,
            date(2026, 10, 20),
            self.manager,
        )

        completed = complete_installation_schedule(
            self.manager,
            schedule.id,
        )

        self.assertEqual(
            completed.status,
            InstallationSchedule.Status.COMPLETED,
        )

        self.assertIsNotNone(
            completed.completed_at,
        )

    def test_installation_can_be_cancelled(self):

        schedule = create_installation_schedule(
            self.manager,
            self.project,
            date(2026, 10, 20),
            self.manager,
        )

        cancelled = cancel_installation_schedule(
            self.manager,
            schedule.id,
        )

        self.assertEqual(
            cancelled.status,
            InstallationSchedule.Status.CANCELLED,
        )

        self.assertIsNotNone(
            cancelled.cancelled_at,
        )

    def test_completed_installation_cannot_be_reopened(self):

        schedule = create_installation_schedule(
            self.manager,
            self.project,
            date(2026, 10, 20),
            self.manager,
        )

        complete_installation_schedule(
            self.manager,
            schedule.id,
        )

        schedule.status = InstallationSchedule.Status.SCHEDULED

        with self.assertRaises(Exception):
            schedule.save()