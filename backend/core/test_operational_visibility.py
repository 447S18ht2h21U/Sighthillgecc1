"""Regression tests for operational project visibility."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from .models import (
    Customer,
    Project,
    ProjectTechnicalAssignment,
    Role,
    User,
)
from .operational_visibility import operational_project_scope


class OperationalVisibilityTests(TestCase):
    def setUp(self):
        self.comptroller = User.objects.create_user(
            username="visibility_comptroller",
            role=Role.COMPTROLLER,
            initials="CP",
        )
        self.manager = User.objects.create_user(
            username="visibility_manager",
            role=Role.SALES_MANAGER,
            initials="SM",
        )
        self.installer = User.objects.create_user(
            username="visibility_installer",
            role=Role.INSTALLATION_MANAGER,
            initials="IM",
        )
        self.sales = User.objects.create_user(
            username="visibility_sales",
            role=Role.SALES_ASSOCIATE,
            initials="SA",
        )
        self.other_sales = User.objects.create_user(
            username="visibility_other_sales",
            role=Role.SALES_ASSOCIATE,
            initials="OS",
        )
        self.technician = User.objects.create_user(
            username="visibility_technician",
            role=Role.TECHNICIAN,
            initials="TA",
        )
        self.other_technician = User.objects.create_user(
            username="visibility_other_technician",
            role=Role.TECHNICIAN,
            initials="OT",
        )
        self.unrelated = User.objects.create_user(
            username="visibility_unrelated",
            role=Role.DATABASE_ADMINISTRATOR,
            initials="DB",
        )

        customer = Customer.objects.create(
            legal_name="Operational Visibility Customer",
            billing_address="10 Example Street",
            created_by=self.comptroller,
        )
        self.project = Project.objects.create(
            code="OP-VIS-001",
            customer=customer,
            location="10 Example Street",
            sales_associate=self.sales,
            reviewer=self.manager,
        )
        self.other_project = Project.objects.create(
            code="OP-VIS-002",
            customer=customer,
            location="12 Example Street",
            sales_associate=self.other_sales,
            reviewer=self.manager,
        )

    def visible_ids(self, user):
        return set(
            operational_project_scope(user).values_list("id", flat=True)
        )

    def assign(self, project, *, effective_date=None, status=None):
        return ProjectTechnicalAssignment.objects.create(
            project=project,
            technical_associate=self.technician,
            assigned_by=self.installer,
            effective_date=effective_date or timezone.localdate(),
            status=status or ProjectTechnicalAssignment.Status.ACTIVE,
        )

    def test_operational_managers_see_all_projects(self):
        expected = {self.project.id, self.other_project.id}
        for user in (self.comptroller, self.manager, self.installer):
            with self.subTest(role=user.role):
                self.assertEqual(self.visible_ids(user), expected)

    def test_sales_associate_sees_only_assigned_projects(self):
        self.assertEqual(self.visible_ids(self.sales), {self.project.id})
        self.assertEqual(
            self.visible_ids(self.other_sales),
            {self.other_project.id},
        )

    def test_technician_sees_only_active_effective_assignments(self):
        self.assign(self.project)
        self.assertEqual(
            self.visible_ids(self.technician),
            {self.project.id},
        )
        self.assertEqual(self.visible_ids(self.other_technician), set())

    def test_future_assignment_does_not_grant_early_access(self):
        self.assign(
            self.project,
            effective_date=timezone.localdate() + timedelta(days=1),
        )
        self.assertEqual(self.visible_ids(self.technician), set())

    def test_ended_assignment_does_not_grant_access(self):
        self.assign(
            self.project,
            status=ProjectTechnicalAssignment.Status.ENDED,
        )
        self.assertEqual(self.visible_ids(self.technician), set())

    def test_unrelated_role_has_no_project_visibility(self):
        self.assertEqual(self.visible_ids(self.unrelated), set())

    def test_inactive_user_has_no_project_visibility(self):
        self.installer.is_active = False
        self.installer.save(update_fields=["is_active"])
        self.assertEqual(self.visible_ids(self.installer), set())

    def test_temporary_installation_manager_authority(self):
        from unittest.mock import patch
        from .temporary_duty_services import request_temporary_duty, approve_temporary_duty, revoke_temporary_duty
        ceo = User.objects.create_user(username='visibility_ceo', role=Role.CEO, initials='CE')
        now = timezone.now()
        authorization = request_temporary_duty(employee=ceo, temporary_role=Role.INSTALLATION_MANAGER, requested_by=ceo, reason='Temporary operational coverage', starts_at=now - timedelta(minutes=1), ends_at=now + timedelta(days=2))
        self.assertEqual(self.visible_ids(ceo), set())
        approved = approve_temporary_duty(authorization_id=authorization.pk, approver=self.comptroller)
        self.assertEqual(
            self.visible_ids(ceo),
            set(),
            'Temporary duty authorization must not independently grant project access.',
        )
        self.assertEqual(ceo.role, Role.CEO)
        with patch('django.utils.timezone.now', return_value=approved.ends_at):
            self.assertEqual(self.visible_ids(ceo), set())
        self.assertEqual(self.visible_ids(ceo), set())
        revoke_temporary_duty(authorization_id=approved.pk, revoked_by=self.comptroller, reason='Coverage ended')
        self.assertEqual(self.visible_ids(ceo), set())

