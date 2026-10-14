from datetime import date

from django.test import TestCase

from .models import (
    Project,
    Customer,
    User,
    Role,
    InstallationSchedule,
    MSR,
    CustomerSignatureEvidence,
    ProjectEvidence,
    CustomerPayment,
)

from .installation_schedule_services import (
    create_installation_schedule,
    complete_installation_schedule,
    cancel_installation_schedule,
)

from .services import create_project


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

        self.sales = User.objects.create_user(
            username='installation_sales_test',
            password='test-password',
            role=Role.SALES_ASSOCIATE,
            initials='SA',
        )

        self.sales_manager = User.objects.create_user(
            username='installation_sales_manager_test',
            password='test-password',
            role=Role.SALES_MANAGER,
            initials='SM',
        )

        self.customer = Customer.objects.create(
            legal_name='Installation Test Customer',
            billing_address='123 Installation Road',
            created_by=self.sales,
        )

        self.project = create_project(
            self.sales,
            self.customer,
            'Installation Test Location',
            self.sales,
            self.sales_manager,
        )

    def make_installation_eligible(self, financed=True):
        from datetime import timedelta
        from django.utils import timezone
        from .services import transition

        self.project.refresh_from_db()

        if self.project.current_approved:
            msr = self.project.current_approved
        else:
            msr = self.project.pending

            msr.snapshot.update({
            'scope': 'Install HVAC equipment',
            'payment_terms': '50% deposit when eligible; balance upon completion.' if financed else '100% due upon completion.',
            'base_price': '10000.00',
            'discount': '0.00',
            'tax': '0.00',
            'total_price': '10000.00',
            'financing_type': 'FINANCED' if financed else 'NON_FINANCED',
            'payment_option': '50_PERCENT_DEPOSIT' if financed else '100_PERCENT_COMPLETION',
        })

            msr = transition(
                self.sales,
                msr.id,
                'edit',
                msr.edit_sequence,
                snapshot=msr.snapshot,
            )

            msr = transition(
                self.sales,
                msr.id,
                'submit',
                msr.edit_sequence,
            )

            msr = transition(
                self.sales_manager,
                msr.id,
                'approve',
                msr.edit_sequence,
            )

            self.project.refresh_from_db()
            msr = self.project.current_approved

        signed_at = timezone.now() - timedelta(days=10)

        for kind in (
            CustomerSignatureEvidence.DocumentKind.CONTRACT,
            CustomerSignatureEvidence.DocumentKind.INVOICE,
        ):
            CustomerSignatureEvidence.objects.get_or_create(
                msr=msr,
                document_kind=kind,
                signer_role=CustomerSignatureEvidence.SignerRole.CUSTOMER,
                digest=f'{kind}-DIGEST',
                defaults={
                    'signer_name': 'Test Customer',
                    'signer_email': 'customer@example.com',
                    'signed_at': signed_at,
                    'provider_reference': 'TEST-ENVELOPE',
                },
            )

        deadline = signed_at + timedelta(days=1)

        ProjectEvidence.objects.create(
            msr=msr,
            kind='CANCELLATION_DEADLINE',
            created_by=self.comptroller,
            data={
                'verified': True,
                'deadline': deadline.isoformat(),
                'snapshot_sha256': 'TEST',
            },
            digest='TEST-DEADLINE-DIGEST',
        )

        if financed:
            payment, created = CustomerPayment.objects.get_or_create(
                project=self.project,
                msr=msr,
                payment_reference='TEST-DEPOSIT',
                defaults={
                    'kind': CustomerPayment.Kind.DEPOSIT,
                    'amount': '5000.00',
                    'received_date': timezone.localdate(),
                    'status': CustomerPayment.Status.PENDING,
                    'recorded_by': self.comptroller,
                },
            )

            if payment.status == CustomerPayment.Status.PENDING:
                from .payment_services import verify_customer_payment
                verify_customer_payment(
                    self.comptroller,
                    payment.id,
                )

        return msr

    def test_installation_can_be_scheduled(self):
        self.make_installation_eligible()

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
        self.make_installation_eligible()

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
        self.make_installation_eligible()

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
        self.make_installation_eligible()

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
        self.make_installation_eligible()
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
        self.make_installation_eligible()

        self.make_installation_eligible()

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
        self.make_installation_eligible()

        self.make_installation_eligible()

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
        self.make_installation_eligible()

        self.make_installation_eligible()

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

        self.make_installation_eligible()

        self.make_installation_eligible()

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
        self.make_installation_eligible()

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
