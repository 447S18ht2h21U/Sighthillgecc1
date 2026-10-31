"""Isolated database-backed tests for MSR project viewing scope."""

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from .access_msr_project_scope import msr_visible_project_scope
from .models import Project, ProjectTechnicalAssignment, Role


class MSRProjectScopeTests(TestCase):
    """Use only Django-created test data; never existing project records."""

    @classmethod
    def setUpTestData(cls):
        # Use saved test projects without touching existing users or customers.
        # Project rows are created through the isolated database only.
        pass

    def actor(self, role, pk=101, active=True, authenticated=True):
        return SimpleNamespace(
            pk=pk,
            role=role,
            is_active=active,
            is_authenticated=authenticated,
        )

    def test_all_project_positions_use_all_scope(self):
        for role in (
            Role.CEO,
            Role.COMPTROLLER,
            Role.MARKETING,
            Role.SALES_MANAGER,
            Role.INSTALLATION_MANAGER,
        ):
            with self.subTest(role=role):
                qs = msr_visible_project_scope(self.actor(role))
                self.assertEqual(qs.model, Project)
                self.assertNotIn("WHERE", str(qs.query))

    def test_sales_associate_is_scoped_to_ownership(self):
        qs = msr_visible_project_scope(
            self.actor(Role.SALES_ASSOCIATE, pk=101)
        )
        self.assertIn("sales_associate_id", str(qs.query))

    def test_technician_requires_active_assignment(self):
        qs = msr_visible_project_scope(
            self.actor(Role.TECHNICIAN, pk=101)
        )
        sql = str(qs.query)
        self.assertIn("technical_associate_id", sql)
        self.assertIn("effective_date", sql)
        self.assertIn("status", sql)

    def test_future_effective_assignment_is_filtered(self):
        with patch("core.access_msr_project_scope.timezone.localdate") as today:
            today.return_value = date(2026, 10, 30)
            qs = msr_visible_project_scope(self.actor(Role.TECHNICIAN))
            self.assertIn("effective_date", str(qs.query))
            today.assert_called_once()

    def test_unassigned_positions_receive_empty_scope(self):
        for role in (
            Role.ACCOUNTS_PAYABLE_ASSOCIATE,
            Role.DATABASE_ADMINISTRATOR,
        ):
            with self.subTest(role=role):
                self.assertFalse(
                    msr_visible_project_scope(self.actor(role)).exists()
                )

    def test_inactive_and_unauthenticated_accounts_denied(self):
        for role in Role.values:
            with self.subTest(role=role):
                self.assertFalse(
                    msr_visible_project_scope(
                        self.actor(role, active=False)
                    ).exists()
                )
                self.assertFalse(
                    msr_visible_project_scope(
                        self.actor(role, authenticated=False)
                    ).exists()
                )

    def test_unknown_actions_and_write_methods_denied(self):
        user = self.actor(Role.CEO)

        for action, method in (
            ("create", "POST"),
            ("change", "POST"),
            ("prepare_signing", "POST"),
            ("prepare_document", "POST"),
            ("history", "GET"),
            ("list", "PATCH"),
            ("retrieve", "DELETE"),
        ):
            with self.subTest(action=action, method=method):
                self.assertFalse(
                    msr_visible_project_scope(
                        user, action=action, method=method
                    ).exists()
                )

    def test_missing_user_denied(self):
        self.assertFalse(msr_visible_project_scope(None).exists())

    def test_missing_actor_id_denied_for_assigned_roles(self):
        for role in (Role.SALES_ASSOCIATE, Role.TECHNICIAN):
            with self.subTest(role=role):
                self.assertFalse(
                    msr_visible_project_scope(
                        self.actor(role, pk=None)
                    ).exists()
                )

class MSRProjectScopeDatabaseTests(TestCase):
    """Check actual project results in Django's isolated test database."""

    def setUp(self):
        from .models import Customer, User

        self.comptroller = User.objects.create_user(
            username="msr_scope_comptroller",
            role=Role.COMPTROLLER,
            initials="CP",
        )
        self.sales_one = User.objects.create_user(
            username="msr_scope_sales_one",
            role=Role.SALES_ASSOCIATE,
            initials="S1",
        )
        self.sales_two = User.objects.create_user(
            username="msr_scope_sales_two",
            role=Role.SALES_ASSOCIATE,
            initials="S2",
        )
        self.technician = User.objects.create_user(
            username="msr_scope_technician",
            role=Role.TECHNICIAN,
            initials="T1",
        )
        self.other_technician = User.objects.create_user(
            username="msr_scope_other_technician",
            role=Role.TECHNICIAN,
            initials="T2",
        )
        self.manager = User.objects.create_user(
            username="msr_scope_installation_manager",
            role=Role.INSTALLATION_MANAGER,
            initials="IM",
        )

        customer = Customer.objects.create(
            legal_name="MSR Scope Fixture Customer",
            billing_address="10 Fixture Road",
            created_by=self.comptroller,
        )

        self.project_one = Project.objects.create(
            code="MSR-SCOPE-001",
            customer=customer,
            location="10 Fixture Road",
            sales_associate=self.sales_one,
            reviewer=self.comptroller,
        )
        self.project_two = Project.objects.create(
            code="MSR-SCOPE-002",
            customer=customer,
            location="12 Fixture Road",
            sales_associate=self.sales_two,
            reviewer=self.comptroller,
        )

    def visible(self, actor):
        return set(
            msr_visible_project_scope(actor).values_list("id", flat=True)
        )

    def assign(self, project, *, technician=None, status=None,
               effective_date=None):
        return ProjectTechnicalAssignment.objects.create(
            project=project,
            technical_associate=technician or self.technician,
            assigned_by=self.manager,
            status=status or ProjectTechnicalAssignment.Status.ACTIVE,
            effective_date=effective_date or timezone.localdate(),
        )

    def test_all_project_roles_receive_both_projects(self):
        from .models import User

        roles = (
            Role.CEO,
            Role.COMPTROLLER,
            Role.MARKETING,
            Role.SALES_MANAGER,
            Role.INSTALLATION_MANAGER,
        )

        for role in roles:
            with self.subTest(role=role):
                actor = User.objects.create_user(
                    username=f"msr_scope_{role.lower()}",
                    role=role,
                ) if role not in (Role.COMPTROLLER, Role.INSTALLATION_MANAGER) else (self.comptroller if role == Role.COMPTROLLER else self.manager)

                self.assertEqual(
                    self.visible(actor),
                    {self.project_one.id, self.project_two.id},
                )

    def test_sales_associates_see_only_their_projects(self):
        self.assertEqual(
            self.visible(self.sales_one),
            {self.project_one.id},
        )
        self.assertEqual(
            self.visible(self.sales_two),
            {self.project_two.id},
        )

    def test_active_technician_sees_only_assigned_project(self):
        self.assign(self.project_one)

        self.assertEqual(
            self.visible(self.technician),
            {self.project_one.id},
        )
        self.assertEqual(
            self.visible(self.other_technician),
            set(),
        )

    def test_future_assignment_does_not_grant_access(self):
        self.assign(
            self.project_one,
            effective_date=timezone.localdate() + timedelta(days=1),
        )

        self.assertEqual(self.visible(self.technician), set())

    def test_ended_assignment_does_not_grant_access(self):
        self.assign(
            self.project_one,
            status=ProjectTechnicalAssignment.Status.ENDED,
        )

        self.assertEqual(self.visible(self.technician), set())

    def test_active_assignment_with_ended_timestamp_does_not_grant_access(self):
        assignment = self.assign(self.project_one)
        assignment.ended_at = timezone.now()
        assignment.save(update_fields=['ended_at'])

        self.assertEqual(
            assignment.status,
            ProjectTechnicalAssignment.Status.ACTIVE,
        )
        self.assertEqual(self.visible(self.technician), set())

    def test_assignment_to_other_technician_does_not_grant_access(self):
        self.assign(
            self.project_one,
            technician=self.other_technician,
        )

        self.assertEqual(self.visible(self.technician), set())
        self.assertEqual(
            self.visible(self.other_technician),
            {self.project_one.id},
        )

    def test_inactive_technician_has_no_visibility(self):
        self.assign(self.project_one)
        self.technician.is_active = False
        self.technician.save(update_fields=["is_active"])

        self.assertEqual(self.visible(self.technician), set())

    def test_unrelated_roles_have_no_visibility(self):
        from .models import User

        for role in (
            Role.ACCOUNTS_PAYABLE_ASSOCIATE,
            Role.DATABASE_ADMINISTRATOR,
        ):
            with self.subTest(role=role):
                actor = User.objects.create_user(
                    username=f"msr_denied_{role.lower()}",
                    role=role,
                )
                self.assertEqual(self.visible(actor), set())

    def test_write_actions_never_return_projects(self):
        self.assertFalse(
            msr_visible_project_scope(
                self.comptroller,
                action="change",
                method="POST",
            ).exists()
        )