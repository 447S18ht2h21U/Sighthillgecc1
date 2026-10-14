"""API regression tests for installation scheduling."""

from django.test import TestCase
from rest_framework.test import APIClient

from .models import (
    Customer,
    InstallationSchedule,
    Project,
    Role,
    User,
    MSR,
    CustomerSignatureEvidence,
    ProjectEvidence,
    CustomerPayment,
)

from .services import create_project


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
        self.sales = User.objects.create_user(
            username="schedule_api_sales",
            password="TestOnlyPassword2026!",
            role=Role.SALES_ASSOCIATE,
            initials="SA",
        )

        self.sales_manager = User.objects.create_user(
            username="schedule_api_sales_manager",
            password="TestOnlyPassword2026!",
            role=Role.SALES_MANAGER,
            initials="SM",
        )

        self.customer = Customer.objects.create(
            legal_name="Installation Schedule API Customer",
            billing_address="123 Test Road",
            created_by=self.sales,
        )

        self.project = create_project(
            self.sales,
            self.customer,
            "Installation Schedule API Location",
            self.sales,
            self.sales_manager,
        )

    def make_installation_eligible(
        self,
        project=None,
        actor=None,
        reviewer=None,
        financed=True,
    ):
        from datetime import timedelta
        from django.utils import timezone
        from .services import transition
        from .payment_services import verify_customer_payment

        project = project or self.project
        actor = actor or self.sales
        reviewer = reviewer or self.sales_manager

        project.refresh_from_db()

        if project.current_approved:
            msr = project.current_approved
        else:
            msr = project.pending

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
                actor,
                msr.id,
                'edit',
                msr.edit_sequence,
                snapshot=msr.snapshot,
            )

            msr = transition(
                actor,
                msr.id,
                'submit',
                msr.edit_sequence,
            )

            msr = transition(
                reviewer,
                msr.id,
                'approve',
                msr.edit_sequence,
            )

            project.refresh_from_db()
            msr = project.current_approved

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

        ProjectEvidence.objects.get_or_create(
            msr=msr,
            kind='CANCELLATION_DEADLINE',
            digest='TEST-DEADLINE-DIGEST',
            defaults={
                'created_by': self.comptroller,
                'data': {
                    'verified': True,
                    'deadline': (signed_at + timedelta(days=1)).isoformat(),
                },
            },
        )

        if financed:
            payment, _ = CustomerPayment.objects.get_or_create(
                project=project,
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
                verify_customer_payment(
                    self.comptroller,
                    payment.id,
                )

        return msr

    def test_schedule_listing_respects_operational_visibility(self):
        from datetime import date
        from .installation_schedule_services import create_installation_schedule

        self.make_installation_eligible()

        visible_schedule = create_installation_schedule(
            actor=self.manager,
            project=self.project,
            scheduled_date=date(2026, 10, 20),
            installation_manager=self.manager,
        )

        other_sales = User.objects.create_user(
            username="schedule_listing_other_sales",
            role=Role.SALES_ASSOCIATE,
            initials="OS",
        )
        other_manager = self.sales_manager

        other_project = create_project(
            other_sales,
            self.customer,
            "Other Installation Location",
            other_sales,
            other_manager,
        )

        self.make_installation_eligible(
            project=other_project,
            actor=other_sales,
            reviewer=self.sales_manager,
        )
        self.make_installation_eligible()

        hidden_schedule = create_installation_schedule(
            actor=self.manager,
            project=other_project,
            scheduled_date=date(2026, 10, 21),
            installation_manager=self.manager,
        )

        self.client.force_authenticate(self.manager)
        response = self.client.get("/api/installation-schedules/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

        self.client.force_authenticate(other_sales)
        response = self.client.get("/api/installation-schedules/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            str(hidden_schedule.pk),
        )
        self.assertNotEqual(
            response.data["results"][0]["id"],
            str(visible_schedule.pk),
        )

    def test_installation_manager_directory_allows_authorized_manager(self):
        self.client.force_authenticate(self.manager)
        response = self.client.get("/api/installation-managers/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            str(self.manager.pk),
            [str(item["id"]) for item in response.data],
        )

    def test_installation_manager_directory_rejects_sales_associate(self):
        sales_user = User.objects.create_user(
            username="directory_unauthorized_sales",
            role=Role.SALES_ASSOCIATE,
        )
        self.client.force_authenticate(sales_user)
        response = self.client.get("/api/installation-managers/")
        self.assertEqual(response.status_code, 403)

    def test_installation_manager_directory_rejects_anonymous_user(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/installation-managers/")
        self.assertIn(response.status_code, (401, 403))

    def test_installation_manager_directory_excludes_inactive_managers(self):
        inactive_manager = User.objects.create_user(
            username="directory_inactive_manager",
            role=Role.INSTALLATION_MANAGER,
            is_active=False,
        )
        self.client.force_authenticate(self.manager)
        response = self.client.get("/api/installation-managers/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            str(inactive_manager.pk),
            [str(item["id"]) for item in response.data],
        )

    def test_unauthenticated_user_cannot_list_schedules(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/installation-schedules/")
        self.assertIn(response.status_code, (401, 403))

    def test_installation_manager_can_schedule(self):
        self.client.force_authenticate(self.manager)
        self.make_installation_eligible()

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
        self.make_installation_eligible()

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
        self.make_installation_eligible()

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

        self.make_installation_eligible()

        self.make_installation_eligible()
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

        self.make_installation_eligible()
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

        self.make_installation_eligible()
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
        from .temporary_project_access_services import (
            request_temporary_project_access,
            approve_temporary_project_access,
        )

        access = request_temporary_project_access(
            employee=temporary_manager,
            temporary_duty=authorization,
            project=self.project,
            requested_by=temporary_manager,
            reason="Project-specific installation scheduling coverage.",
            starts_at=now,
            ends_at=now + timedelta(days=1),
        )
        approve_temporary_project_access(
            authorization_id=access.pk,
            approver=self.comptroller,
        )

        self.client.force_authenticate(temporary_manager)
        self.make_installation_eligible()

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

    def test_project_access_required_for_all_schedule_actions(self):
        from datetime import date
        from unittest.mock import patch
        from .installation_schedule_services import create_installation_schedule

        self.make_installation_eligible()
        schedule = create_installation_schedule(
            actor=self.manager,
            project=self.project,
            scheduled_date=date(2026, 10, 20),
            installation_manager=self.manager,
        )

        self.client.force_authenticate(self.manager)

        with patch(
            "core.installation_schedule_services.operational_project_scope"
        ) as scope:
            from .models import Project
            scope.return_value = Project.objects.none()

            create_response = self.client.post(
                "/api/installation-schedules/",
                {
                    "project": str(self.project.pk),
                    "scheduled_date": "2026-10-21",
                    "installation_manager": str(self.manager.pk),
                },
                format="json",
            )
            self.assertEqual(create_response.status_code, 403)

            for operation in ("complete", "cancel"):
                with self.subTest(operation=operation):
                    response = self.client.post(
                        f"/api/installation-schedules/{schedule.pk}/{operation}/",
                        {},
                        format="json",
                    )
                    self.assertEqual(response.status_code, 403)

        self.assertEqual(InstallationSchedule.objects.count(), 1)
        schedule.refresh_from_db()
        self.assertEqual(schedule.status, InstallationSchedule.Status.SCHEDULED)
        self.assertIsNone(schedule.completed_at)
        self.assertIsNone(schedule.cancelled_at)

    def test_ceo_without_temporary_authorization_cannot_schedule(self):
        ceo = User.objects.create_user(
            username="schedule_api_ceo_without_authorization",
            password="TestOnlyPassword2026!",
            role=Role.CEO,
        )
        self.client.force_authenticate(ceo)
        self.make_installation_eligible()

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
