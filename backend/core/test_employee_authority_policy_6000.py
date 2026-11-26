"""Approved employee authority policy tests."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from rest_framework.exceptions import PermissionDenied

from .models import Role

from .employee_authority_policy_6000 import (
    ACTIVE_DEPLOYMENT_ROLES,
    DEFERRED_DEPLOYMENT_ROLES,
    UPLOAD_DISTRIBUTOR_INVOICE,
    VERIFY_DISTRIBUTOR_INVOICE,
    ALLOCATE_EXISTING_INVOICE,
    role_enabled_for_initial_deployment,
    distributor_invoice_action_allowed,
    require_distributor_invoice_authority,
)

from . import distributor_invoice_services_5999 as services


class EmployeeAuthorityTests6000(SimpleTestCase):

    def actor(self, role, active=True, authenticated=True):
        return SimpleNamespace(
            pk="test-employee",
            role=role,
            is_active=active,
            is_authenticated=authenticated,
        )

    def test_six_operational_roles(self):
        self.assertEqual(
            ACTIVE_DEPLOYMENT_ROLES,
            {
                Role.CEO,
                Role.COMPTROLLER,
                Role.SALES_MANAGER,
                Role.SALES_ASSOCIATE,
                Role.INSTALLATION_MANAGER,
                Role.TECHNICIAN,
            },
        )

    def test_three_deferred_roles(self):
        self.assertEqual(
            DEFERRED_DEPLOYMENT_ROLES,
            {
                Role.MARKETING,
                Role.ACCOUNTS_PAYABLE_ASSOCIATE,
                Role.DATABASE_ADMINISTRATOR,
            },
        )

    def test_role_definitions_preserved(self):
        self.assertEqual(
            ACTIVE_DEPLOYMENT_ROLES |
            DEFERRED_DEPLOYMENT_ROLES,
            set(Role.values),
        )

        self.assertFalse(
            ACTIVE_DEPLOYMENT_ROLES &
            DEFERRED_DEPLOYMENT_ROLES
        )

    def test_upload_authority_matrix(self):
        for role in Role.values:
            with self.subTest(role=role):
                self.assertEqual(
                    distributor_invoice_action_allowed(
                        role,
                        UPLOAD_DISTRIBUTOR_INVOICE,
                    ),
                    role in {
                        Role.INSTALLATION_MANAGER,
                        Role.COMPTROLLER,
                    },
                )

    def test_verification_authority_matrix(self):
        for role in Role.values:
            with self.subTest(role=role):
                self.assertEqual(
                    distributor_invoice_action_allowed(
                        role,
                        VERIFY_DISTRIBUTOR_INVOICE,
                    ),
                    role in {
                        Role.INSTALLATION_MANAGER,
                        Role.CEO,
                    },
                )

    def test_allocation_authority_matrix(self):
        for role in Role.values:
            with self.subTest(role=role):
                self.assertEqual(
                    distributor_invoice_action_allowed(
                        role,
                        ALLOCATE_EXISTING_INVOICE,
                    ),
                    role in {
                        Role.COMPTROLLER,
                        Role.CEO,
                    },
                )

    def test_deferred_roles_denied(self):
        for role in DEFERRED_DEPLOYMENT_ROLES:
            self.assertFalse(
                role_enabled_for_initial_deployment(role)
            )

            for action in (
                UPLOAD_DISTRIBUTOR_INVOICE,
                VERIFY_DISTRIBUTOR_INVOICE,
                ALLOCATE_EXISTING_INVOICE,
            ):
                self.assertFalse(
                    distributor_invoice_action_allowed(
                        role,
                        action,
                    )
                )

    def test_unknown_roles_denied(self):
        for role in ("", None, "UNKNOWN", [], {}):
            self.assertFalse(
                role_enabled_for_initial_deployment(role)
            )

    def test_unknown_actions_denied(self):
        for action in ("", None, "UNKNOWN", [], {}):
            self.assertFalse(
                distributor_invoice_action_allowed(
                    Role.CEO,
                    action,
                )
            )

    def test_inactive_employee_denied(self):
        actor = self.actor(
            Role.COMPTROLLER,
            active=False,
        )

        with self.assertRaises(PermissionDenied):
            require_distributor_invoice_authority(
                actor,
                UPLOAD_DISTRIBUTOR_INVOICE,
            )

    def test_unauthenticated_employee_denied(self):
        actor = self.actor(
            Role.INSTALLATION_MANAGER,
            authenticated=False,
        )

        with self.assertRaises(PermissionDenied):
            require_distributor_invoice_authority(
                actor,
                UPLOAD_DISTRIBUTOR_INVOICE,
            )

    def test_ceo_upload_denied(self):
        with self.assertRaises(PermissionDenied):
            require_distributor_invoice_authority(
                self.actor(Role.CEO),
                UPLOAD_DISTRIBUTOR_INVOICE,
            )

    def test_comptroller_upload_permitted(self):
        actor = self.actor(Role.COMPTROLLER)

        self.assertIs(
            require_distributor_invoice_authority(
                actor,
                UPLOAD_DISTRIBUTOR_INVOICE,
            ),
            actor,
        )

    def test_comptroller_purchase_verification_denied(self):
        with self.assertRaises(PermissionDenied):
            require_distributor_invoice_authority(
                self.actor(Role.COMPTROLLER),
                VERIFY_DISTRIBUTOR_INVOICE,
            )

    def test_installation_manager_cross_project_denied(self):
        with self.assertRaises(PermissionDenied):
            require_distributor_invoice_authority(
                self.actor(Role.INSTALLATION_MANAGER),
                ALLOCATE_EXISTING_INVOICE,
            )

    def test_server_reloads_employee_role(self):
        browser_actor = self.actor(Role.COMPTROLLER)
        actual_actor = self.actor(Role.CEO)

        with patch.object(
            services.User.objects,
            "select_for_update",
        ) as query:

            query.return_value.filter.return_value.first.return_value = (
                actual_actor
            )

            with self.assertRaises(PermissionDenied):
                services._actor(
                    browser_actor,
                    UPLOAD_DISTRIBUTOR_INVOICE,
                )

    def test_server_rejects_missing_active_employee(self):
        actor = self.actor(Role.COMPTROLLER)

        with patch.object(
            services.User.objects,
            "select_for_update",
        ) as query:

            query.return_value.filter.return_value.first.return_value = (
                None
            )

            with self.assertRaises(PermissionDenied):
                services._actor(
                    actor,
                    UPLOAD_DISTRIBUTOR_INVOICE,
                )

    def test_installation_manager_assignment_restriction(self):
        actor = self.actor(Role.INSTALLATION_MANAGER)

        project = SimpleNamespace(
            state="APPROVED",
            pk="test-project",
        )

        with patch.object(
            services.Project.objects,
            "select_for_update",
        ) as projects:

            projects.return_value.filter.return_value.first.return_value = (
                project
            )

            with patch.object(
                services.InstallationSchedule.objects,
                "filter",
            ) as schedules:

                schedules.return_value.exists.return_value = False

                with self.assertRaises(PermissionDenied):
                    services._project(
                        actor,
                        project.pk,
                    )
