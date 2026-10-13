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
    def test_unauthorized_employee_cannot_complete_or_cancel(self):
        from rest_framework.exceptions import PermissionDenied

        associate = User.objects.create_user(
            username='unauthorized_installation_associate',
            password='test-password',
            role=Role.SALES_ASSOCIATE,
            initials='UA',
        )

        schedule = create_installation_schedule(
            self.manager,
            self.project,
            date(2026, 10, 20),
            self.manager,
        )

        with self.assertRaises(PermissionDenied):
            complete_installation_schedule(associate, schedule.id)

        with self.assertRaises(PermissionDenied):
            cancel_installation_schedule(associate, schedule.id)

        schedule.refresh_from_db()
        self.assertEqual(schedule.status, InstallationSchedule.Status.SCHEDULED)
        self.assertIsNone(schedule.completed_at)
        self.assertIsNone(schedule.cancelled_at)

    def test_expired_temporary_installation_authority_is_rejected(self):
        from datetime import timedelta
        from unittest.mock import patch
        from django.utils import timezone
        from rest_framework.exceptions import PermissionDenied
        from .temporary_duty_services import request_temporary_duty, approve_temporary_duty

        ceo = User.objects.create_user(
            username='expired_installation_ceo',
            role=Role.CEO,
            initials='CE',
        )
        now = timezone.now()
        authorization = request_temporary_duty(
            employee=ceo,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=ceo,
            reason='Temporary installation coverage',
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=2),
        )
        approved = approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )
        schedule = create_installation_schedule(
            self.manager, self.project, date(2026, 10, 20), self.manager,
        )
        with patch("django.utils.timezone.now", return_value=approved.ends_at):
            with self.assertRaises(PermissionDenied):
                complete_installation_schedule(ceo, schedule.id)
            with self.assertRaises(PermissionDenied):
                cancel_installation_schedule(ceo, schedule.id)
        schedule.refresh_from_db()
        self.assertEqual(schedule.status, InstallationSchedule.Status.SCHEDULED)
        self.assertIsNone(schedule.completed_at)
        self.assertIsNone(schedule.cancelled_at)

    def test_revoked_temporary_installation_authority_is_rejected(self):
        from datetime import timedelta
        from django.utils import timezone
        from rest_framework.exceptions import PermissionDenied
        from .temporary_duty_services import request_temporary_duty, approve_temporary_duty, revoke_temporary_duty

        ceo = User.objects.create_user(
            username='revoked_installation_ceo',
            role=Role.CEO,
            initials='CE',
        )
        now = timezone.now()
        authorization = request_temporary_duty(
            employee=ceo,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=ceo,
            reason='Temporary installation coverage',
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=2),
        )
        approved = approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )
        schedule = create_installation_schedule(
            self.manager, self.project, date(2026, 10, 20), self.manager,
        )
        revoke_temporary_duty(
            authorization_id=approved.pk,
            revoked_by=self.comptroller,
            reason='Coverage ended',
        )
        with self.assertRaises(PermissionDenied):
            complete_installation_schedule(ceo, schedule.id)
        with self.assertRaises(PermissionDenied):
            cancel_installation_schedule(ceo, schedule.id)
        schedule.refresh_from_db()
        self.assertEqual(schedule.status, InstallationSchedule.Status.SCHEDULED)
        self.assertIsNone(schedule.completed_at)
        self.assertIsNone(schedule.cancelled_at)

    def test_temporary_installation_completion_is_audited(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import AuditEvent, TemporaryDutyActivity
        from .temporary_duty_services import request_temporary_duty, approve_temporary_duty

        ceo = User.objects.create_user(
            username='audited_installation_ceo',
            role=Role.CEO,
            initials='CE',
        )
        now = timezone.now()
        authorization = request_temporary_duty(
            employee=ceo,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=ceo,
            reason='Temporary installation coverage',
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=2),
        )
        approved = approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )
        schedule = create_installation_schedule(
            self.manager, self.project, date(2026, 10, 20), self.manager,
        )
        completed = complete_installation_schedule(ceo, schedule.id)
        self.assertEqual(completed.status, InstallationSchedule.Status.COMPLETED)
        event = AuditEvent.objects.get(
            action='installation_schedule.completed',
            entity_id=schedule.id,
        )
        self.assertEqual(event.actor_id, ceo.id)
        self.assertEqual(
            event.payload['temporary_duty_authorization_id'],
            str(approved.pk),
        )
        activity = TemporaryDutyActivity.objects.get(audit_event=event)
        self.assertEqual(activity.authorization_id, approved.pk)
        self.assertEqual(activity.employee_id, ceo.id)
        self.assertEqual(ceo.role, Role.CEO)

    def test_inactive_installation_manager_cannot_modify_schedules(self):
        from rest_framework.exceptions import PermissionDenied

        schedule = create_installation_schedule(
            self.manager, self.project, date(2026, 10, 20), self.manager,
        )
        self.manager.is_active = False
        self.manager.save(update_fields=['is_active'])

        with self.assertRaises(PermissionDenied):
            create_installation_schedule(
                self.manager, self.project, date(2026, 10, 21), self.manager,
            )
        with self.assertRaises(PermissionDenied):
            complete_installation_schedule(self.manager, schedule.id)
        with self.assertRaises(PermissionDenied):
            cancel_installation_schedule(self.manager, schedule.id)

        schedule.refresh_from_db()
        self.assertEqual(schedule.status, InstallationSchedule.Status.SCHEDULED)
        self.assertIsNone(schedule.completed_at)
        self.assertIsNone(schedule.cancelled_at)
        self.assertEqual(InstallationSchedule.objects.count(), 1)

    def test_temporary_installation_scheduling_is_audited(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import AuditEvent, TemporaryDutyActivity
        from .temporary_duty_services import request_temporary_duty, approve_temporary_duty

        ceo = User.objects.create_user(
            username='scheduling_temporary_ceo',
            role=Role.CEO,
            initials='CE',
        )
        now = timezone.now()
        authorization = request_temporary_duty(
            employee=ceo,
            temporary_role=Role.INSTALLATION_MANAGER,
            requested_by=ceo,
            reason='Temporary installation scheduling coverage',
            starts_at=now - timedelta(minutes=1),
            ends_at=now + timedelta(days=2),
        )
        approved = approve_temporary_duty(
            authorization_id=authorization.pk,
            approver=self.comptroller,
        )
        schedule = create_installation_schedule(
            ceo, self.project, date(2026, 10, 20), self.manager,
        )
        self.assertEqual(schedule.status, InstallationSchedule.Status.SCHEDULED)
        self.assertEqual(schedule.scheduled_by_id, ceo.id)
        self.assertEqual(schedule.installation_manager_id, self.manager.id)
        event = AuditEvent.objects.get(
            action='installation_schedule.created',
            entity_id=schedule.id,
        )
        self.assertEqual(event.actor_id, ceo.id)
        self.assertEqual(
            event.payload['temporary_duty_authorization_id'],
            str(approved.pk),
        )
        activity = TemporaryDutyActivity.objects.get(audit_event=event)
        self.assertEqual(activity.authorization_id, approved.pk)
        self.assertEqual(activity.employee_id, ceo.id)
        self.assertEqual(ceo.role, Role.CEO)
